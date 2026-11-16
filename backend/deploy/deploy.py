"""Deploy with the AWS CLI using the caller's standard AWS credential environment.

Never accepts or prints provider keys. Run after building .deploy/lambda.zip.
"""
import argparse,hashlib,json,subprocess,time
from pathlib import Path

def aws(*args,optional=False):
    r=subprocess.run(['aws',*args,'--output','json'],capture_output=True,text=True)
    if r.returncode:
        if optional:return None
        raise RuntimeError('AWS CLI failed: '+r.stderr[:500])
    return json.loads(r.stdout) if r.stdout.strip() else {}

def main():
    p=argparse.ArgumentParser();p.add_argument('--zip',required=True);p.add_argument('--origin',required=True);args=p.parse_args()
    region='us-east-1'
    account=aws('sts','get-caller-identity')['Account']
    name='campus-university-rag';role=name+'-runtime';table='campus-rag-limits'
    archive=Path(args.zip).resolve()
    bucket=f'campus-rag-deploy-{account}-{region}'
    if aws('s3api','head-bucket','--bucket',bucket,optional=True) is None:
        # head-bucket succeeds with an empty object, so also tolerate an already-owned bucket.
        aws('s3api','create-bucket','--bucket',bucket,optional=True)
    aws('s3api','put-public-access-block','--bucket',bucket,'--public-access-block-configuration','BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true')
    aws('s3api','put-bucket-encryption','--bucket',bucket,'--server-side-encryption-configuration',json.dumps({'Rules':[{'ApplyServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]}))
    aws('s3api','put-bucket-lifecycle-configuration','--bucket',bucket,'--lifecycle-configuration',json.dumps({'Rules':[{'ID':'expire-build-artifacts','Status':'Enabled','Filter':{'Prefix':'releases/'},'Expiration':{'Days':7}}]}))
    artifact='releases/'+hashlib.sha256(archive.read_bytes()).hexdigest()[:16]+'.zip'
    aws('s3api','put-object','--bucket',bucket,'--key',artifact,'--body',str(archive),'--server-side-encryption','AES256')
    provider=aws('secretsmanager','describe-secret','--secret-id','campus-rag/gemini')['ARN']
    trust={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]}
    iam=aws('iam','get-role','--role-name',role,optional=True)
    if not iam:iam=aws('iam','create-role','--role-name',role,'--assume-role-policy-document',json.dumps(trust))
    policy={'Version':'2012-10-17','Statement':[
        {'Effect':'Allow','Action':['logs:CreateLogGroup','logs:CreateLogStream','logs:PutLogEvents'],'Resource':f'arn:aws:logs:{region}:{account}:log-group:/aws/lambda/{name}:*'},
        {'Effect':'Allow','Action':['secretsmanager:GetSecretValue'],'Resource':provider},
        {'Effect':'Allow','Action':['dynamodb:GetItem','dynamodb:PutItem','dynamodb:UpdateItem'],'Resource':f'arn:aws:dynamodb:{region}:{account}:table/{table}'},
    ]}
    aws('iam','put-role-policy','--role-name',role,'--policy-name','campus-runtime-only','--policy-document',json.dumps(policy))
    if not aws('dynamodb','describe-table','--table-name',table,optional=True):
        aws('dynamodb','create-table','--table-name',table,'--attribute-definitions','AttributeName=pk,AttributeType=S','--key-schema','AttributeName=pk,KeyType=HASH','--billing-mode','PAY_PER_REQUEST')
        aws('dynamodb','wait','table-exists','--table-name',table)
        aws('dynamodb','update-time-to-live','--table-name',table,'--time-to-live-specification','Enabled=true,AttributeName=expires_at')
    release=hashlib.sha256(archive.read_bytes()).hexdigest()[:12]
    env={'Variables':{'AWS_LAMBDA_EXEC_WRAPPER':'/opt/bootstrap','AWS_LWA_INVOKE_MODE':'response_stream','AWS_LWA_READINESS_CHECK_PATH':'/health','PORT':'8000','RAG_ALLOWED_ORIGINS':args.origin,'RAG_PROVIDER_SECRET':provider,'RAG_LIMIT_TABLE':table,'RAG_DAILY_LIMIT':'100','GEMINI_MODEL':'gemini-3.1-flash-lite','RAG_RELEASE':release,'PYTHONUNBUFFERED':'1'}}
    layer=f'arn:aws:lambda:{region}:753240598075:layer:LambdaAdapterLayerX86:30'
    if aws('lambda','get-function','--function-name',name,optional=True):
        aws('lambda','update-function-code','--function-name',name,'--s3-bucket',bucket,'--s3-key',artifact)
        aws('lambda','wait','function-updated','--function-name',name)
        aws('lambda','update-function-configuration','--function-name',name,'--runtime','python3.12','--handler','run.sh','--timeout','180','--memory-size','1792','--layers',layer,'--environment',json.dumps(env))
    else:
        # IAM propagation can take several seconds; retry only the role-assumption error.
        for attempt in range(8):
            try:
                aws('lambda','create-function','--function-name',name,'--runtime','python3.12','--role',iam['Role']['Arn'],'--handler','run.sh','--timeout','180','--memory-size','1792','--layers',layer,'--environment',json.dumps(env),'--code',json.dumps({'S3Bucket':bucket,'S3Key':artifact}))
                break
            except RuntimeError as e:
                if 'cannot be assumed' not in str(e) or attempt==7:raise
                time.sleep(3)
    aws('lambda','wait','function-updated','--function-name',name)
    reservation=aws('lambda','put-function-concurrency','--function-name',name,'--reserved-concurrent-executions','2',optional=True)
    url=aws('lambda','get-function-url-config','--function-name',name,optional=True)
    if not url:url=aws('lambda','create-function-url-config','--function-name',name,'--auth-type','NONE','--invoke-mode','RESPONSE_STREAM')
    for sid,action,extra in [('public-url','lambda:InvokeFunctionUrl',['--function-url-auth-type','NONE']),('url-invoke-only','lambda:InvokeFunction',['--invoked-via-function-url'])]:
        aws('lambda','add-permission','--function-name',name,'--statement-id',sid,'--action',action,'--principal','*',*extra,optional=True)
    aws('logs','put-retention-policy','--log-group-name','/aws/lambda/'+name,'--retention-in-days','7',optional=True)
    result={'function':name,'region':region,'url':url['FunctionUrl'],'invoke_mode':url['InvokeMode'],'daily_request_limit':100,'reserved_concurrency':reservation.get('ReservedConcurrentExecutions') if reservation else None}
    output=Path('.deploy/deployment.json');output.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
