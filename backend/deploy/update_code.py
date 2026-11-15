"""Fast code-only redeployment after deploy.py has provisioned the resources."""
import argparse,hashlib,json
from pathlib import Path
from .deploy import aws

p=argparse.ArgumentParser();p.add_argument('--zip',default='.deploy/lambda.zip');args=p.parse_args()
path=Path(args.zip).resolve();digest=hashlib.sha256(path.read_bytes()).hexdigest()
account=aws('sts','get-caller-identity')['Account'];bucket=f'campus-rag-deploy-{account}-us-east-1';key='releases/'+digest[:16]+'.zip'
aws('s3api','put-object','--bucket',bucket,'--key',key,'--body',str(path),'--server-side-encryption','AES256')
aws('lambda','update-function-code','--function-name','campus-university-rag','--s3-bucket',bucket,'--s3-key',key)
aws('lambda','wait','function-updated','--function-name','campus-university-rag')
config=aws('lambda','get-function-configuration','--function-name','campus-university-rag')
env=config['Environment']['Variables'];env['RAG_RELEASE']=digest[:12]
aws('lambda','update-function-configuration','--function-name','campus-university-rag','--environment',json.dumps({'Variables':env}))
aws('lambda','wait','function-updated','--function-name','campus-university-rag')
print('Updated Lambda artifact:',digest[:12])
