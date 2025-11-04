import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
import time
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify

from config import Config
from storage.buffer import SampleBuffer
from drift.baseline import BaselineManager
from drift.detector import DriftDetector
from alerts.alerter import AlertDispatcher
from model.model import SimpleModel


def create_app():
    app = Flask(__name__)

    # Configure logging
    logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    app.logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))

    # Initialize components
    sample_buffer = SampleBuffer(maxlen=Config.DRIFT_WINDOW_SIZE)
    baseline_manager = BaselineManager(Config.BASELINE_PATH, num_bins=Config.NUM_BINS)
    detector = DriftDetector(baseline_manager, Config)
    alerter = AlertDispatcher(Config)
    model = SimpleModel()

    state = {
        'last_report': None,
        'last_alert_ts': 0.0
    }

    # Background drift checker
    def drift_checker():
        while True:
            try:
                time.sleep(Config.DRIFT_CHECK_INTERVAL_SECONDS)
                baseline = baseline_manager.get()
                samples = sample_buffer.get_samples()
                if not baseline:
                    app.logger.debug('Baseline not set yet; skipping drift check.')
                    continue
                if len(samples) < max(50, Config.NUM_BINS * 5):
                    app.logger.debug('Not enough samples for drift check (have %d).', len(samples))
                    continue
                report = detector.compute_report(samples)
                state['last_report'] = report

                drift_detected = report['summary']['drift_detected']
                severity = report['summary']['severity']
                now_ts = time.time()

                if drift_detected and severity in ('high', 'warn'):
                    if now_ts - state['last_alert_ts'] >= Config.ALERT_COOLDOWN_SECONDS:
                        try:
                            alerter.send_alert(report)
                            state['last_alert_ts'] = now_ts
                        except Exception:
                            app.logger.exception('Failed to send alert')
                    else:
                        app.logger.info('Drift detected but in cooldown window; no alert sent.')
            except Exception:
                app.logger.exception('Error in drift checker loop')

    t = threading.Thread(target=drift_checker, daemon=True)
    t.start()

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok', 'time': datetime.now(timezone.utc).isoformat()})

    @app.route('/predict', methods=['POST'])
    def predict():
        payload = request.get_json(force=True, silent=True) or {}
        features = payload.get('features')
        if not isinstance(features, dict):
            return jsonify({'error': 'Payload must include features as an object'}), 400
        try:
            pred = model.predict(features)
            sample_buffer.add_sample(features, float(pred))
            return jsonify({'prediction': float(pred)})
        except Exception as e:
            app.logger.exception('Prediction failed')
            return jsonify({'error': str(e)}), 500

    @app.route('/drift/report', methods=['GET'])
    def drift_report():
        report = state['last_report']
        if not report:
            return jsonify({'message': 'No report yet'}), 404
        return jsonify(report)

    @app.route('/drift/trigger', methods=['POST'])
    def drift_trigger():
        baseline = baseline_manager.get()
        if not baseline:
            return jsonify({'error': 'Baseline not set'}), 400
        samples = sample_buffer.get_samples()
        if len(samples) < max(50, Config.NUM_BINS * 5):
            return jsonify({'error': f'Not enough samples to compute drift. Need at least {max(50, Config.NUM_BINS * 5)}'}), 400
        report = detector.compute_report(samples)
        state['last_report'] = report
        return jsonify(report)

    @app.route('/baseline/init', methods=['POST'])
    def baseline_init():
        payload = request.get_json(force=True, silent=True) or {}
        records = payload.get('records')
        if not isinstance(records, list) or len(records) == 0:
            return jsonify({'error': 'Provide records: [{"features": {...}, "prediction": optional}]'}), 400
        # Ensure predictions exist
        normalized = []
        for r in records:
            feats = r.get('features') if isinstance(r, dict) else None
            if not isinstance(feats, dict):
                return jsonify({'error': 'Each record must include features object'}), 400
            pred = r.get('prediction')
            if pred is None:
                pred = model.predict(feats)
            normalized.append({'features': feats, 'prediction': float(pred)})
        baseline = baseline_manager.build_baseline(normalized)
        baseline_manager.set(baseline)
        return jsonify({'message': 'Baseline initialized', 'summary': baseline_manager.summary()})

    @app.route('/baseline/status', methods=['GET'])
    def baseline_status():
        baseline = baseline_manager.get()
        if not baseline:
            return jsonify({'message': 'Baseline not set'}), 404
        return jsonify({'summary': baseline_manager.summary(), 'path': baseline_manager.path})

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port)



@app.route('/reset', methods=['POST'])
def _auto_stub_reset():
    return 'Auto-generated stub for /reset', 200
