from typing import Tuple, Any, Dict
from jsonschema import validate, Draft7Validator
from jsonschema.exceptions import ValidationError

INVENTORY_SCHEMA: Dict[str, Any] = {
    'type': 'object',
    'properties': {
        'org': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'jurisdictions': {
                    'type': 'array',
                    'items': {'type': 'string'}
                },
                'requires_dpo': {'type': 'boolean'},
                'dpo_assigned': {'type': 'boolean'}
            },
            'required': ['jurisdictions']
        },
        'datasets': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'category': {'type': 'string', 'enum': ['personal', 'sensitive', 'non-personal']},
                    'fields': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string'},
                                'type': {'type': 'string'},
                                'pii': {'type': 'boolean'},
                                'sensitive': {'type': 'boolean'},
                                'purpose': {'type': 'array', 'items': {'type': 'string'}}
                            },
                            'required': ['name']
                        }
                    },
                    'lawful_basis': {'type': ['string', 'null'], 'enum': [
                        'consent', 'contract', 'legal_obligation', 'legitimate_interests', 'public_task', 'vital_interests', None
                    ]},
                    'consent_management': {
                        'type': 'object',
                        'properties': {
                            'consent_recorded': {'type': 'boolean'},
                            'refresh_interval_days': {'type': 'integer', 'minimum': 0}
                        }
                    },
                    'lia_conducted': {'type': 'boolean'},
                    'dpia_conducted': {'type': 'boolean'},
                    'systematic_monitoring': {'type': 'boolean'},
                    'large_scale': {'type': 'boolean'},
                    'retention_period_days': {'type': ['integer', 'null']},
                    'location': {'type': ['string', 'null']},
                    'transfers': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'recipient_country': {'type': 'string'},
                                'safeguard': {'type': ['string', 'null']}
                            },
                            'required': ['recipient_country']
                        }
                    },
                    'processor': {'type': 'boolean'},
                    'processor_name': {'type': ['string', 'null']},
                    'dpa_in_place': {'type': 'boolean'},
                    'processing_activities_purpose': {'type': ['string', 'null']},
                    'sell_share_to_third_parties': {'type': 'boolean'},
                    'targeted_advertising': {'type': 'boolean'},
                    'dsar_covered': {'type': 'boolean'},
                    'security_measures': {'type': 'array', 'items': {'type': 'string'}},
                    'encryption_at_rest': {'type': 'boolean'},
                    'pseudonymization': {'type': 'boolean'},
                    'children_data': {'type': 'boolean'},
                    'age_known': {'type': 'boolean'},
                    'notice_at_collection': {'type': 'boolean'},
                    'access_controls': {'type': 'array', 'items': {'type': 'string'}}
                },
                'required': ['name', 'category']
            }
        },
        'cookies': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'purpose': {'type': 'string', 'enum': ['strictly_necessary', 'analytics', 'advertising', 'functional']},
                    'duration_days': {'type': 'integer', 'minimum': 0},
                    'prior_consent': {'type': 'boolean'}
                },
                'required': ['name', 'purpose']
            }
        },
        'dsar': {
            'type': 'object',
            'properties': {
                'contact_channel': {'type': ['string', 'null']},
                'response_time_days': {'type': 'integer', 'minimum': 0},
                'verification_process': {'type': 'boolean'},
                'deletion_supported': {'type': 'boolean'},
                'opt_out_mechanism': {'type': 'boolean'},
                'limit_use_sensitive_info_mechanism': {'type': 'boolean'}
            }
        },
        'retention_policy': {
            'type': 'object',
            'properties': {
                'default_max_days': {'type': ['integer', 'null']},
                'retention_review_interval_days': {'type': ['integer', 'null']},
                'deletion_window_days': {'type': ['integer', 'null']}
            }
        },
        'breach': {
            'type': 'object',
            'properties': {
                'detection_time_hours': {'type': ['integer', 'null']},
                'notification_procedure': {'type': 'boolean'}
            }
        },
        'ropa': {
            'type': 'object',
            'properties': {
                'maintained': {'type': 'boolean'},
                'last_updated_days': {'type': ['integer', 'null']}
            }
        }
    },
    'required': ['org', 'datasets']
}


def validate_inventory(payload: Dict[str, Any]) -> Tuple[bool, Any]:
    try:
        v = Draft7Validator(INVENTORY_SCHEMA)
        errors = sorted(v.iter_errors(payload), key=lambda e: e.path)
        if errors:
            return False, [format_error(e) for e in errors]
        return True, None
    except ValidationError as e:
        return False, [format_error(e)]


def format_error(e: ValidationError) -> Dict[str, Any]:
    return {
        'message': e.message,
        'path': list(e.path),
        'schema_path': list(e.schema_path)
    }

