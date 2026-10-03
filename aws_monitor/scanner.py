"""Thread-safe AWS resource scanner — covers billable services per region."""
import boto3
from botocore.config import Config

SHORT = Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 1})

REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1", "eu-north-1",
    "ap-south-1", "ap-south-2", "ap-northeast-1", "ap-northeast-2",
    "ap-northeast-3", "ap-southeast-1", "ap-southeast-2",
    "sa-east-1", "ca-central-1", "me-south-1", "af-south-1",
]


def _client(svc, region, access, secret):
    return boto3.client(
        svc, region_name=region,
        aws_access_key_id=access, aws_secret_access_key=secret,
        config=SHORT,
    )


def check_creds(access: str, secret: str) -> str:
    """Validate creds via STS. Returns account id or raises."""
    sts = boto3.client(
        "sts", aws_access_key_id=access, aws_secret_access_key=secret,
        region_name="us-east-1", config=SHORT,
    )
    return sts.get_caller_identity().get("Account", "")


def scan_region(region: str, access: str, secret: str):
    """Return list of (service, resource, detail, state, region). Never raises."""
    out = []

    def add(svc, rid, detail="", state=""):
        out.append((svc, str(rid), str(detail), str(state), region))

    # EC2 instances
    try:
        ec2 = _client("ec2", region, access, secret)
        for r in ec2.describe_instances().get("Reservations", []):
            for i in r.get("Instances", []):
                if i["State"]["Name"] == "terminated":
                    continue
                add("EC2", i["InstanceId"], i.get("InstanceType", ""),
                    i["State"]["Name"])
    except Exception:
        pass
    # EBS
    try:
        for v in ec2.describe_volumes().get("Volumes", []):
            add("EBS", v["VolumeId"], f"{v.get('Size')}GiB {v.get('VolumeType')}",
                v.get("State", ""))
    except Exception:
        pass
    # EIP
    try:
        for a in ec2.describe_addresses().get("Addresses", []):
            add("EIP", a.get("PublicIp", a.get("AllocationId", "?")),
                a.get("InstanceId", "unattached"), "in-use")
    except Exception:
        pass
    # NAT gateways (costly if forgotten)
    try:
        for n in ec2.describe_nat_gateways().get("NatGateways", []):
            if n.get("State") != "deleted":
                add("NAT-GW", n.get("NatGatewayId"), n.get("SubnetId", ""),
                    n.get("State", ""))
    except Exception:
        pass
    # Load balancers v2
    try:
        elb = _client("elbv2", region, access, secret)
        for lb in elb.describe_load_balancers().get("LoadBalancers", []):
            add("ELBv2", lb["LoadBalancerName"], lb.get("Type", ""),
                lb.get("State", {}).get("Code", "active"))
    except Exception:
        pass
    # Classic ELB
    try:
        elb1 = _client("elb", region, access, secret)
        for lb in elb1.describe_load_balancers().get("LoadBalancerDescriptions", []):
            add("ELB", lb["LoadBalancerName"], lb.get("Scheme", ""), "active")
    except Exception:
        pass
    # Auto Scaling
    try:
        asg = _client("autoscaling", region, access, secret)
        for g in asg.describe_auto_scaling_groups().get("AutoScalingGroups", []):
            add("ASG", g["AutoScalingGroupName"],
                f"desired={g.get('DesiredCapacity')}", "active")
    except Exception:
        pass
    # RDS instances
    try:
        rds = _client("rds", region, access, secret)
        for d in rds.describe_db_instances().get("DBInstances", []):
            add("RDS", d["DBInstanceIdentifier"], d.get("Engine", ""),
                d.get("DBInstanceStatus", ""))
        try:
            for c in rds.describe_db_clusters().get("DBClusters", []):
                add("RDS-cluster", c.get("DBClusterIdentifier"),
                    c.get("Engine", ""), c.get("Status", ""))
        except Exception:
            pass
    except Exception:
        pass
    # ElastiCache
    try:
        ec = _client("elasticache", region, access, secret)
        for c in ec.describe_cache_clusters().get("CacheClusters", []):
            if c.get("CacheClusterStatus") != "deleted":
                add("ElastiCache", c["CacheClusterId"],
                    c.get("CacheNodeType", ""), c.get("CacheClusterStatus", ""))
    except Exception:
        pass
    # Lambda
    try:
        lam = _client("lambda", region, access, secret)
        for f in lam.list_functions().get("Functions", []):
            add("Lambda", f["FunctionName"], f.get("Runtime", ""),
                f.get("State", "Active"))
    except Exception:
        pass
    # ECS clusters + services
    try:
        ecs = _client("ecs", region, access, secret)
        arns = ecs.list_clusters().get("clusterArns", [])
        for a in arns:
            name = a.split("/")[-1]
            add("ECS-cluster", name, "", "active")
            try:
                svcs = ecs.list_services(cluster=a).get("serviceArns", [])
                for s in svcs:
                    add("ECS-service", s.split("/")[-1], f"cluster={name}", "active")
            except Exception:
                pass
    except Exception:
        pass
    # DynamoDB
    try:
        dd = _client("dynamodb", region, access, secret)
        for t in dd.list_tables().get("TableNames", []):
            try:
                d = dd.describe_table(TableName=t).get("Table", {})
                add("DynamoDB", t, f"{d.get('BillingModeSummary', {}).get('BillingMode', '')}",
                    d.get("TableStatus", ""))
            except Exception:
                add("DynamoDB", t, "", "")
    except Exception:
        pass
    # SNS
    try:
        sns = _client("sns", region, access, secret)
        for t in sns.list_topics().get("Topics", []):
            add("SNS", t["TopicArn"].split(":")[-1], "", "active")
    except Exception:
        pass
    # SQS
    try:
        sqs = _client("sqs", region, access, secret)
        for u in sqs.list_queues().get("QueueUrls", []):
            add("SQS", u.split("/")[-1], "", "active")
    except Exception:
        pass
    # CloudFormation stacks
    try:
        cf = _client("cloudformation", region, access, secret)
        for s in cf.describe_stacks().get("Stacks", []):
            if "DELETE_COMPLETE" not in s.get("StackStatus", ""):
                add("CFN", s["StackName"], "", s.get("StackStatus", ""))
    except Exception:
        pass
    # CloudWatch alarms
    try:
        cw = _client("cloudwatch", region, access, secret)
        for a in cw.describe_alarms().get("MetricAlarms", []):
            add("CW-alarm", a["AlarmName"], "", a.get("StateValue", ""))
    except Exception:
        pass
    # EFS
    try:
        efs = _client("efs", region, access, secret)
        for f in efs.describe_file_systems().get("FileSystems", []):
            if f.get("LifeCycleState") != "deleted":
                add("EFS", f["FileSystemId"], "", f.get("LifeCycleState", ""))
    except Exception:
        pass

    return out


def scan_s3_global(access: str, secret: str):
    out = []
    try:
        s3 = boto3.client("s3", aws_access_key_id=access,
                          aws_secret_access_key=secret, config=SHORT)
        for b in s3.list_buckets().get("Buckets", []):
            name = b["Name"]
            try:
                loc = s3.get_bucket_location(Bucket=name).get("LocationConstraint") or "us-east-1"
            except Exception:
                loc = "?"
            out.append(("S3", name, "", "active", loc))
    except Exception:
        pass
    return out


def scan_iam_global(access: str, secret: str):
    out = []
    try:
        iam = boto3.client("iam", aws_access_key_id=access,
                           aws_secret_access_key=secret, config=SHORT)
        for u in iam.list_users().get("Users", []):
            out.append(("IAM-user", u["UserName"], "", "global", "global"))
        for r in iam.list_roles().get("Roles", [])[:200]:
            if "AWSServiceRole" not in r["RoleName"]:
                out.append(("IAM-role", r["RoleName"], "", "global", "global"))
    except Exception:
        pass
    return out


def scan_route53_global(access: str, secret: str):
    out = []
    try:
        r53 = boto3.client("route53", aws_access_key_id=access,
                           aws_secret_access_key=secret, config=SHORT)
        for z in r53.list_hosted_zones().get("HostedZones", []):
            out.append(("Route53", z["Name"], z["Id"].split("/")[-1], "active", "global"))
    except Exception:
        pass
    return out
