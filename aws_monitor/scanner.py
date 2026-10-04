"""Thread-safe AWS resource scanner — covers billable services per region.

Every scan function accepts an optional `log` callback and narrates
each step ("us-east-1 · EC2: 4 found"), so the UI log shows exactly
what is being scanned, region by region, service by service.
"""
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

# Every scannable service. S3 / IAM / Route53 are global (one job each),
# everything else runs once per region.
SERVICE_LABELS = [
    "EC2", "EBS", "EIP", "NAT-GW", "ELBv2", "ELB", "ASG", "RDS",
    "ElastiCache", "Lambda", "ECS", "DynamoDB", "SNS", "SQS", "CFN",
    "CW-alarm", "EFS", "S3", "IAM", "Route53",
]
GLOBAL_SERVICES = ("S3", "IAM", "Route53")
GLOBAL_KINDS = {"S3": "s3", "IAM": "iam", "Route53": "route53"}
REGIONAL_SERVICES = [s for s in SERVICE_LABELS if s not in GLOBAL_SERVICES]


def _client(svc, region, access, secret):
    return boto3.client(
        svc, region_name=region,
        aws_access_key_id=access, aws_secret_access_key=secret,
        config=SHORT,
    )


def _short(e) -> str:
    msg = str(e).strip().split("\n")[0][:100]
    return msg or type(e).__name__


def _emit(log, msg: str) -> None:
    if log is not None:
        try:
            log(msg)
        except Exception:
            pass


def check_creds(access: str, secret: str) -> str:
    """Validate creds via STS. Returns account id or raises."""
    sts = boto3.client(
        "sts", aws_access_key_id=access, aws_secret_access_key=secret,
        region_name="us-east-1", config=SHORT,
    )
    return sts.get_caller_identity().get("Account", "")


def scan_region(region: str, access: str, secret: str, log=None, services=None):
    """Return list of (service, resource, detail, state, region). Never raises.

    services: None (or empty) = all regional services, else only those labels.
    """
    out = []

    def add(svc, rid, detail="", state=""):
        out.append((svc, str(rid), str(detail), str(state), region))

    def run(svc, fn):
        if services and svc not in services:
            return
        before = len(out)
        try:
            fn()
        except Exception as e:
            _emit(log, f"{region} · {svc}: skipped ({_short(e)})")
            return
        _emit(log, f"{region} · {svc}: {len(out) - before} found")

    # EC2 instances
    def do_ec2():
        ec2 = _client("ec2", region, access, secret)
        for r in ec2.describe_instances().get("Reservations", []):
            for i in r.get("Instances", []):
                if i["State"]["Name"] == "terminated":
                    continue
                add("EC2", i["InstanceId"], i.get("InstanceType", ""),
                    i["State"]["Name"])
    run("EC2", do_ec2)

    # EBS volumes
    def do_ebs():
        ec2 = _client("ec2", region, access, secret)
        for v in ec2.describe_volumes().get("Volumes", []):
            add("EBS", v["VolumeId"], f"{v.get('Size')}GiB {v.get('VolumeType')}",
                v.get("State", ""))
    run("EBS", do_ebs)

    # Elastic IPs
    def do_eip():
        ec2 = _client("ec2", region, access, secret)
        for a in ec2.describe_addresses().get("Addresses", []):
            add("EIP", a.get("PublicIp", a.get("AllocationId", "?")),
                a.get("InstanceId", "unattached"), "in-use")
    run("EIP", do_eip)

    # NAT gateways (costly if forgotten)
    def do_nat():
        ec2 = _client("ec2", region, access, secret)
        for n in ec2.describe_nat_gateways().get("NatGateways", []):
            if n.get("State") != "deleted":
                add("NAT-GW", n.get("NatGatewayId"), n.get("SubnetId", ""),
                    n.get("State", ""))
    run("NAT-GW", do_nat)

    # Load balancers v2
    def do_elbv2():
        elb = _client("elbv2", region, access, secret)
        for lb in elb.describe_load_balancers().get("LoadBalancers", []):
            add("ELBv2", lb["LoadBalancerName"], lb.get("Type", ""),
                lb.get("State", {}).get("Code", "active"))
    run("ELBv2", do_elbv2)

    # Classic ELB
    def do_elb():
        elb1 = _client("elb", region, access, secret)
        for lb in elb1.describe_load_balancers().get("LoadBalancerDescriptions", []):
            add("ELB", lb["LoadBalancerName"], lb.get("Scheme", ""), "active")
    run("ELB", do_elb)

    # Auto Scaling
    def do_asg():
        asg = _client("autoscaling", region, access, secret)
        for g in asg.describe_auto_scaling_groups().get("AutoScalingGroups", []):
            add("ASG", g["AutoScalingGroupName"],
                f"desired={g.get('DesiredCapacity')}", "active")
    run("ASG", do_asg)

    # RDS instances + clusters
    def do_rds():
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
    run("RDS", do_rds)

    # ElastiCache
    def do_elasticache():
        ec = _client("elasticache", region, access, secret)
        for c in ec.describe_cache_clusters().get("CacheClusters", []):
            if c.get("CacheClusterStatus") != "deleted":
                add("ElastiCache", c["CacheClusterId"],
                    c.get("CacheNodeType", ""), c.get("CacheClusterStatus", ""))
    run("ElastiCache", do_elasticache)

    # Lambda
    def do_lambda():
        lam = _client("lambda", region, access, secret)
        for f in lam.list_functions().get("Functions", []):
            add("Lambda", f["FunctionName"], f.get("Runtime", ""),
                f.get("State", "Active"))
    run("Lambda", do_lambda)

    # ECS clusters + services
    def do_ecs():
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
    run("ECS", do_ecs)

    # DynamoDB
    def do_ddb():
        dd = _client("dynamodb", region, access, secret)
        for t in dd.list_tables().get("TableNames", []):
            try:
                d = dd.describe_table(TableName=t).get("Table", {})
                add("DynamoDB", t, f"{d.get('BillingModeSummary', {}).get('BillingMode', '')}",
                    d.get("TableStatus", ""))
            except Exception:
                add("DynamoDB", t, "", "")
    run("DynamoDB", do_ddb)

    # SNS
    def do_sns():
        sns = _client("sns", region, access, secret)
        for t in sns.list_topics().get("Topics", []):
            add("SNS", t["TopicArn"].split(":")[-1], "", "active")
    run("SNS", do_sns)

    # SQS
    def do_sqs():
        sqs = _client("sqs", region, access, secret)
        for u in sqs.list_queues().get("QueueUrls", []):
            add("SQS", u.split("/")[-1], "", "active")
    run("SQS", do_sqs)

    # CloudFormation stacks
    def do_cfn():
        cf = _client("cloudformation", region, access, secret)
        for s in cf.describe_stacks().get("Stacks", []):
            if "DELETE_COMPLETE" not in s.get("StackStatus", ""):
                add("CFN", s["StackName"], "", s.get("StackStatus", ""))
    run("CFN", do_cfn)

    # CloudWatch alarms
    def do_cw():
        cw = _client("cloudwatch", region, access, secret)
        for a in cw.describe_alarms().get("MetricAlarms", []):
            add("CW-alarm", a["AlarmName"], "", a.get("StateValue", ""))
    run("CW-alarm", do_cw)

    # EFS
    def do_efs():
        efs = _client("efs", region, access, secret)
        for f in efs.describe_file_systems().get("FileSystems", []):
            if f.get("LifeCycleState") != "deleted":
                add("EFS", f["FileSystemId"], "", f.get("LifeCycleState", ""))
    run("EFS", do_efs)

    return out


def scan_s3_global(access: str, secret: str, log=None):
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
    except Exception as e:
        _emit(log, f"global · S3: skipped ({_short(e)})")
        return out
    _emit(log, f"global · S3: {len(out)} bucket(s)")
    return out


def scan_iam_global(access: str, secret: str, log=None):
    out = []
    try:
        iam = boto3.client("iam", aws_access_key_id=access,
                           aws_secret_access_key=secret, config=SHORT)
        for u in iam.list_users().get("Users", []):
            out.append(("IAM-user", u["UserName"], "", "global", "global"))
        for r in iam.list_roles().get("Roles", [])[:200]:
            if "AWSServiceRole" not in r["RoleName"]:
                out.append(("IAM-role", r["RoleName"], "", "global", "global"))
    except Exception as e:
        _emit(log, f"global · IAM: skipped ({_short(e)})")
        return out
    _emit(log, f"global · IAM: {len(out)} user(s)/role(s)")
    return out


def scan_route53_global(access: str, secret: str, log=None):
    out = []
    try:
        r53 = boto3.client("route53", aws_access_key_id=access,
                           aws_secret_access_key=secret, config=SHORT)
        for z in r53.list_hosted_zones().get("HostedZones", []):
            out.append(("Route53", z["Name"], z["Id"].split("/")[-1], "active", "global"))
    except Exception as e:
        _emit(log, f"global · Route53: skipped ({_short(e)})")
        return out
    _emit(log, f"global · Route53: {len(out)} zone(s)")
    return out
