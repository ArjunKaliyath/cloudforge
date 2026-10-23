[CmdletBinding()]
param(
    [string]$Profile = "arjun",
    [string]$Region = "us-east-1",
    [bool]$BrokenMode = $false,
    [string]$LocalImage = "cloudforge-orders-worker:local",
    [string]$ImageTag = (Get-Date -Format "yyyyMMdd-HHmmss")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$clusterName = "cloudforge"
$serviceName = "orders-worker"
$repositoryName = "cloudforge-orders-worker"
$taskFamily = "cloudforge-orders-worker"
$executionRoleName = "cloudforge-ecs-execution-role"
$taskRoleName = "cloudforge-orders-task-role"
$logGroupName = "/ecs/cloudforge/orders-worker"
$securityGroupName = "cloudforge-orders-worker"
$queueName = "cloudforge-orders-queue"
$awsBase = @("--profile", $Profile, "--region", $Region, "--output", "json")
$temporaryFiles = [System.Collections.Generic.List[string]]::new()
$temporaryDirectories = [System.Collections.Generic.List[string]]::new()

function Invoke-AwsJson {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $output = & aws @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($output -join [Environment]::NewLine)
    }
    $text = $output -join "`n"
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }
    return $text | ConvertFrom-Json
}

function Write-TemporaryJson {
    param([Parameter(Mandatory)]$Value)

    $path = Join-Path ([System.IO.Path]::GetTempPath()) ("cloudforge-{0}.json" -f [guid]::NewGuid())
    $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8NoBOM
    $temporaryFiles.Add($path)
    return $path
}

function New-CloudForgeTemporaryDirectory {
    $temporaryRoot = (Resolve-Path -LiteralPath ([System.IO.Path]::GetTempPath())).Path.TrimEnd('\')
    $path = Join-Path $temporaryRoot ("cloudforge-{0}" -f [guid]::NewGuid())
    $directory = New-Item -ItemType Directory -Path $path
    $resolved = (Resolve-Path -LiteralPath $directory.FullName).Path
    if ((Split-Path -Parent $resolved).TrimEnd('\') -ne $temporaryRoot) {
        throw "Temporary directory escaped the system temporary folder."
    }
    $temporaryDirectories.Add($resolved)
    return $resolved
}

try {
    $identity = Invoke-AwsJson (@("sts", "get-caller-identity") + $awsBase)
    $accountId = $identity.Account

    $queueUrlResponse = Invoke-AwsJson (@("sqs", "get-queue-url", "--queue-name", $queueName) + $awsBase)
    $queueAttributes = Invoke-AwsJson (@(
        "sqs", "get-queue-attributes",
        "--queue-url", $queueUrlResponse.QueueUrl,
        "--attribute-names", "QueueArn"
    ) + $awsBase)
    $queueArn = $queueAttributes.Attributes.QueueArn

    $vpcs = Invoke-AwsJson (@(
        "ec2", "describe-vpcs",
        "--filters", "Name=is-default,Values=true"
    ) + $awsBase)
    $vpc = $vpcs.Vpcs | Select-Object -First 1
    $vpcId = $vpc.VpcId
    if (-not $vpcId) {
        throw "No default VPC found in $Region."
    }

    $subnetResponse = Invoke-AwsJson (@(
        "ec2", "describe-subnets",
        "--filters", "Name=vpc-id,Values=$vpcId", "Name=default-for-az,Values=true"
    ) + $awsBase)
    $subnetIds = @($subnetResponse.Subnets | Sort-Object AvailabilityZone | Select-Object -ExpandProperty SubnetId)
    if ($subnetIds.Count -lt 2) {
        throw "Fargate deployment requires at least two default subnets."
    }

    $repositories = Invoke-AwsJson (@("ecr", "describe-repositories") + $awsBase)
    $repository = $repositories.repositories |
        Where-Object repositoryName -eq $repositoryName |
        Select-Object -First 1
    if (-not $repository) {
        $repositoryResponse = Invoke-AwsJson (@(
            "ecr", "create-repository",
            "--repository-name", $repositoryName,
            "--image-scanning-configuration", "scanOnPush=true",
            "--tags", "Key=Project,Value=CloudForge"
        ) + $awsBase)
        $repository = $repositoryResponse.repository
    }
    $imageUri = "$($repository.repositoryUri):$ImageTag"

    $dockerConfigDirectory = New-CloudForgeTemporaryDirectory
    $registryPassword = & aws ecr get-login-password --profile $Profile --region $Region
    if ($LASTEXITCODE -ne 0) {
        throw "Could not retrieve an ECR login password."
    }
    $registryHost = "$accountId.dkr.ecr.$Region.amazonaws.com"
    $registryAuth = [Convert]::ToBase64String(
        [Text.Encoding]::UTF8.GetBytes("AWS:$registryPassword")
    )
    @{
        auths = @{
            $registryHost = @{ auth = $registryAuth }
        }
    } | ConvertTo-Json -Depth 5 | Set-Content (
        Join-Path $dockerConfigDirectory "config.json"
    ) -Encoding utf8NoBOM
    docker tag $LocalImage $imageUri
    if ($LASTEXITCODE -ne 0) {
        throw "Local image '$LocalImage' was not found. Build it before deploying."
    }
    docker --config $dockerConfigDirectory push $imageUri
    if ($LASTEXITCODE -ne 0) {
        throw "Docker could not push '$imageUri'."
    }

    $logGroups = Invoke-AwsJson (@(
        "logs", "describe-log-groups",
        "--log-group-name-prefix", $logGroupName
    ) + $awsBase)
    if (-not @($logGroups.logGroups | Where-Object logGroupName -eq $logGroupName)) {
        Invoke-AwsJson (@("logs", "create-log-group", "--log-group-name", $logGroupName) + $awsBase) | Out-Null
    }
    Invoke-AwsJson (@(
        "logs", "put-retention-policy",
        "--log-group-name", $logGroupName,
        "--retention-in-days", "7"
    ) + $awsBase) | Out-Null

    $trustPolicy = @{
        Version = "2012-10-17"
        Statement = @(@{
            Effect = "Allow"
            Principal = @{ Service = "ecs-tasks.amazonaws.com" }
            Action = "sts:AssumeRole"
            Condition = @{
                StringEquals = @{ "aws:SourceAccount" = $accountId }
                ArnLike = @{ "aws:SourceArn" = "arn:aws:ecs:${Region}:${accountId}:*" }
            }
        })
    }
    $trustPolicyPath = Write-TemporaryJson $trustPolicy
    $roles = Invoke-AwsJson (@("iam", "list-roles") + $awsBase)
    $createdRole = $false

    if (-not @($roles.Roles | Where-Object RoleName -eq $executionRoleName)) {
        Invoke-AwsJson (@(
            "iam", "create-role",
            "--role-name", $executionRoleName,
            "--assume-role-policy-document", "file://$trustPolicyPath",
            "--tags", "Key=Project,Value=CloudForge"
        ) + $awsBase) | Out-Null
        $createdRole = $true
    }
    Invoke-AwsJson (@(
        "iam", "attach-role-policy",
        "--role-name", $executionRoleName,
        "--policy-arn", "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
    ) + $awsBase) | Out-Null

    if (-not @($roles.Roles | Where-Object RoleName -eq $taskRoleName)) {
        Invoke-AwsJson (@(
            "iam", "create-role",
            "--role-name", $taskRoleName,
            "--assume-role-policy-document", "file://$trustPolicyPath",
            "--tags", "Key=Project,Value=CloudForge"
        ) + $awsBase) | Out-Null
        $createdRole = $true
    }
    $taskPolicy = @{
        Version = "2012-10-17"
        Statement = @(@{
            Sid = "ConsumeCloudForgeOrders"
            Effect = "Allow"
            Action = @(
                "sqs:GetQueueUrl",
                "sqs:GetQueueAttributes",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage"
            )
            Resource = $queueArn
        })
    }
    $taskPolicyPath = Write-TemporaryJson $taskPolicy
    Invoke-AwsJson (@(
        "iam", "put-role-policy",
        "--role-name", $taskRoleName,
        "--policy-name", "cloudforge-orders-queue-consumer",
        "--policy-document", "file://$taskPolicyPath"
    ) + $awsBase) | Out-Null

    if ($createdRole) {
        Start-Sleep -Seconds 10
    }
    $executionRole = Invoke-AwsJson (@("iam", "get-role", "--role-name", $executionRoleName) + $awsBase)
    $taskRole = Invoke-AwsJson (@("iam", "get-role", "--role-name", $taskRoleName) + $awsBase)

    $clusters = Invoke-AwsJson (@("ecs", "list-clusters") + $awsBase)
    if (-not @($clusters.clusterArns | Where-Object { $_ -match "/$clusterName$" })) {
        Invoke-AwsJson (@(
            "ecs", "create-cluster",
            "--cluster-name", $clusterName,
            "--tags", "key=Project,value=CloudForge"
        ) + $awsBase) | Out-Null
    }

    $securityGroups = Invoke-AwsJson (@(
        "ec2", "describe-security-groups",
        "--filters", "Name=vpc-id,Values=$vpcId", "Name=group-name,Values=$securityGroupName"
    ) + $awsBase)
    $securityGroup = $securityGroups.SecurityGroups | Select-Object -First 1
    $securityGroupId = if ($null -ne $securityGroup) { $securityGroup.GroupId } else { $null }
    if (-not $securityGroupId) {
        $securityGroup = Invoke-AwsJson (@(
            "ec2", "create-security-group",
            "--group-name", $securityGroupName,
            "--description", "Outbound-only security group for the CloudForge orders worker",
            "--vpc-id", $vpcId
        ) + $awsBase)
        $securityGroupId = $securityGroup.GroupId
    }

    $taskDefinition = @{
        family = $taskFamily
        taskRoleArn = $taskRole.Role.Arn
        executionRoleArn = $executionRole.Role.Arn
        networkMode = "awsvpc"
        requiresCompatibilities = @("FARGATE")
        cpu = "256"
        memory = "512"
        runtimePlatform = @{
            cpuArchitecture = "X86_64"
            operatingSystemFamily = "LINUX"
        }
        containerDefinitions = @(@{
            name = "orders-worker"
            image = $imageUri
            essential = $true
            readonlyRootFilesystem = $true
            stopTimeout = 30
            command = @("worker")
            environment = @(
                @{ name = "AWS_DEFAULT_REGION"; value = $Region },
                @{ name = "BROKEN_MODE"; value = $BrokenMode.ToString().ToLowerInvariant() }
            )
            logConfiguration = @{
                logDriver = "awslogs"
                options = @{
                    "awslogs-group" = $logGroupName
                    "awslogs-region" = $Region
                    "awslogs-stream-prefix" = "ecs"
                    mode = "blocking"
                }
            }
        })
    }
    $taskDefinitionPath = Write-TemporaryJson $taskDefinition
    $registered = Invoke-AwsJson (@(
        "ecs", "register-task-definition",
        "--cli-input-json", "file://$taskDefinitionPath"
    ) + $awsBase)
    $taskDefinitionArn = $registered.taskDefinition.taskDefinitionArn

    $services = Invoke-AwsJson (@(
        "ecs", "describe-services",
        "--cluster", $clusterName,
        "--services", $serviceName
    ) + $awsBase)
    $existingService = $services.services |
        Where-Object status -ne "INACTIVE" |
        Select-Object -First 1
    $deploymentConfiguration = "deploymentCircuitBreaker={enable=true,rollback=true},maximumPercent=200,minimumHealthyPercent=100"
    if ($existingService) {
        Invoke-AwsJson (@(
            "ecs", "update-service",
            "--cluster", $clusterName,
            "--service", $serviceName,
            "--task-definition", $taskDefinitionArn,
            "--desired-count", "1",
            "--deployment-configuration", $deploymentConfiguration
        ) + $awsBase) | Out-Null
    }
    else {
        $networkConfiguration = "awsvpcConfiguration={subnets=[$($subnetIds -join ',')],securityGroups=[$securityGroupId],assignPublicIp=ENABLED}"
        Invoke-AwsJson (@(
            "ecs", "create-service",
            "--cluster", $clusterName,
            "--service-name", $serviceName,
            "--task-definition", $taskDefinitionArn,
            "--desired-count", "1",
            "--launch-type", "FARGATE",
            "--platform-version", "LATEST",
            "--network-configuration", $networkConfiguration,
            "--deployment-configuration", $deploymentConfiguration,
            "--tags", "key=Project,value=CloudForge"
        ) + $awsBase) | Out-Null
    }

    & aws ecs wait services-stable --cluster $clusterName --services $serviceName --profile $Profile --region $Region
    if ($LASTEXITCODE -ne 0) {
        throw "The ECS service did not reach a stable state."
    }
    $finalService = Invoke-AwsJson (@(
        "ecs", "describe-services",
        "--cluster", $clusterName,
        "--services", $serviceName
    ) + $awsBase)
    $service = $finalService.services | Select-Object -First 1
    [pscustomobject]@{
        Cluster = $clusterName
        Service = $serviceName
        TaskDefinition = $taskDefinitionArn
        Image = $imageUri
        BrokenMode = $BrokenMode
        DesiredTasks = $service.desiredCount
        RunningTasks = $service.runningCount
        LogGroup = $logGroupName
        SecurityGroup = $securityGroupId
    } | ConvertTo-Json
}
finally {
    foreach ($temporaryFile in $temporaryFiles) {
        Remove-Item -LiteralPath $temporaryFile -Force -ErrorAction SilentlyContinue
    }
    foreach ($temporaryDirectory in $temporaryDirectories) {
        $resolvedDirectory = (Resolve-Path -LiteralPath $temporaryDirectory -ErrorAction SilentlyContinue).Path
        if ($resolvedDirectory -and $resolvedDirectory -eq $temporaryDirectory) {
            Remove-Item -LiteralPath $resolvedDirectory -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
