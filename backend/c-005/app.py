import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request

app = Flask(__name__)

scaffolds = {
    "react-native": {
        "name": "React Native",
        "files": [
            {"path": "App.js", "content": "import React from 'react';\nimport { Text, View } from 'react-native';\n\nexport default function App() {\n  return (\n    <View>\n      <Text>Hello React Native!</Text>\n    </View>\n  );\n}"},
            {"path": "package.json", "content": "{\n  \"name\": \"mobile-app\",\n  \"dependencies\": {\n    \"react\": \"18.2.0\",\n    \"react-native\": \"0.72.0\"\n  }\n}"}
        ]
    },
    "flutter": {
        "name": "Flutter",
        "files": [
            {"path": "lib/main.dart", "content": "import 'package:flutter/material.dart';\n\nvoid main() {\n  runApp(MyApp());\n}\n\nclass MyApp extends StatelessWidget {\n  @override\n  Widget build(BuildContext context) {\n    return MaterialApp(\n      home: Scaffold(\n        body: Center(\n          child: Text('Hello Flutter!'),\n        ),\n      ),\n    );\n  }\n}"},
            {"path": "pubspec.yaml", "content": "name: mobile_app\ndescription: A Flutter mobile app\nversion: 1.0.0\n\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n\ndependencies:\n  flutter:\n    sdk: flutter"}
        ]
    }
}

@app.route('/')
def home():
    return jsonify({"message": "Mobile Scaffolds API", "frameworks": list(scaffolds.keys())})

@app.route('/scaffolds', methods=['GET'])
def get_scaffolds():
    return jsonify({"scaffolds": list(scaffolds.keys())})

@app.route('/scaffolds/<framework>', methods=['GET'])
def get_scaffold(framework):
    if framework not in scaffolds:
        return jsonify({"error": "Framework not found"}), 404
    return jsonify(scaffolds[framework])

@app.route('/generate', methods=['POST'])
def generate_scaffold():
    data = request.get_json()
    framework = data.get('framework')
    
    if not framework:
        return jsonify({"error": "Framework is required"}), 400
    
    if framework not in scaffolds:
        return jsonify({"error": "Framework not supported"}), 404
    
    return jsonify({"success": True, "scaffold": scaffolds[framework]})

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/scaffolds/react-native', methods=['GET'])
def _auto_stub_scaffolds_react_native():
    return 'Auto-generated stub for /scaffolds/react-native', 200


@app.route('/scaffolds/vue-native', methods=['GET'])
def _auto_stub_scaffolds_vue_native():
    return 'Auto-generated stub for /scaffolds/vue-native', 200
