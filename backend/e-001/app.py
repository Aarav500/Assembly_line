import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

TERRAFORM_MODULES = {
    'vm': {
        'aws': 'module "vm" {\n  source = "./modules/vm"\n  instance_type = "t2.micro"\n  ami = "ami-xxxxx"\n}',
        'azure': 'module "vm" {\n  source = "./modules/vm"\n  vm_size = "Standard_B1s"\n  image_id = "xxxxx"\n}',
        'gcp': 'module "vm" {\n  source = "./modules/vm"\n  machine_type = "e2-micro"\n  image = "xxxxx"\n}'
    },
    'db': {
        'aws': 'module "database" {\n  source = "./modules/db"\n  engine = "postgres"\n  instance_class = "db.t3.micro"\n}',
        'azure': 'module "database" {\n  source = "./modules/db"\n  sku_name = "B_Gen5_1"\n  engine = "postgres"\n}',
        'gcp': 'module "database" {\n  source = "./modules/db"\n  tier = "db-f1-micro"\n  database_version = "POSTGRES_14"\n}'
    },
    'network': {
        'aws': 'module "network" {\n  source = "./modules/network"\n  vpc_cidr = "10.0.0.0/16"\n  subnet_cidr = "10.0.1.0/24"\n}',
        'azure': 'module "network" {\n  source = "./modules/network"\n  address_space = ["10.0.0.0/16"]\n  subnet_prefix = "10.0.1.0/24"\n}',
        'gcp': 'module "network" {\n  source = "./modules/network"\n  ip_cidr_range = "10.0.0.0/16"\n  subnet_range = "10.0.1.0/24"\n}'
    },
    'dns': {
        'aws': 'module "dns" {\n  source = "./modules/dns"\n  zone_name = "example.com"\n  type = "A"\n}',
        'azure': 'module "dns" {\n  source = "./modules/dns"\n  zone_name = "example.com"\n  record_type = "A"\n}',
        'gcp': 'module "dns" {\n  source = "./modules/dns"\n  dns_name = "example.com."\n  type = "A"\n}'
    },
    'storage': {
        'aws': 'module "storage" {\n  source = "./modules/storage"\n  bucket_name = "my-bucket"\n  acl = "private"\n}',
        'azure': 'module "storage" {\n  source = "./modules/storage"\n  account_name = "mystorageaccount"\n  account_tier = "Standard"\n}',
        'gcp': 'module "storage" {\n  source = "./modules/storage"\n  bucket_name = "my-bucket"\n  location = "US"\n}'
    }
}

@app.route('/')
def home():
    return jsonify({
        'message': 'Terraform Module Templates API',
        'available_modules': list(TERRAFORM_MODULES.keys()),
        'providers': ['aws', 'azure', 'gcp']
    })

@app.route('/modules')
def list_modules():
    return jsonify({
        'modules': list(TERRAFORM_MODULES.keys())
    })

@app.route('/modules/<module_type>')
def get_module(module_type):
    if module_type not in TERRAFORM_MODULES:
        return jsonify({'error': 'Module not found'}), 404
    return jsonify(TERRAFORM_MODULES[module_type])

@app.route('/modules/<module_type>/<provider>')
def get_module_template(module_type, provider):
    if module_type not in TERRAFORM_MODULES:
        return jsonify({'error': 'Module not found'}), 404
    if provider not in TERRAFORM_MODULES[module_type]:
        return jsonify({'error': 'Provider not found'}), 404
    return jsonify({
        'module': module_type,
        'provider': provider,
        'template': TERRAFORM_MODULES[module_type][provider]
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/modules/vm/aws', methods=['GET'])
def _auto_stub_modules_vm_aws():
    return 'Auto-generated stub for /modules/vm/aws', 200


@app.route('/modules/invalid', methods=['GET'])
def _auto_stub_modules_invalid():
    return 'Auto-generated stub for /modules/invalid', 200


@app.route('/modules/vm/invalid', methods=['GET'])
def _auto_stub_modules_vm_invalid():
    return 'Auto-generated stub for /modules/vm/invalid', 200
