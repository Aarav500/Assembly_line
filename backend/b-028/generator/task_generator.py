import re
import uuid
from datetime import datetime
from collections import Counter


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TaskGenerator:
    def __init__(self):
        # Map canonical features to keywords and epic templates
        self.catalog = {
            'authentication': {
                'keywords': ['login', 'log in', 'sign in', 'signup', 'sign up', 'auth', 'authenticate', 'password', 'oauth', 'account', 'user account', '2fa', 'mfa'],
                'epic': {
                    'title': 'Authentication & Accounts',
                    'description': 'Enable users to securely sign up, sign in, and manage their accounts.'
                }
            },
            'content': {
                'keywords': ['create', 'edit', 'update', 'delete', 'crud', 'manage', 'organize', 'catalog', 'library', 'post', 'record', 'item', 'entry'],
                'epic': {
                    'title': 'Core Content Management',
                    'description': 'Create, read, update, and delete core domain content.'
                }
            },
            'search': {
                'keywords': ['search', 'filter', 'find', 'lookup', 'discover'],
                'epic': {
                    'title': 'Search & Discovery',
                    'description': 'Help users find relevant content quickly via search and filters.'
                }
            },
            'notifications': {
                'keywords': ['notify', 'notification', 'email', 'push', 'sms', 'alert'],
                'epic': {
                    'title': 'Notifications & Alerts',
                    'description': 'Keep users informed with timely notifications and preferences.'
                }
            },
            'reporting': {
                'keywords': ['report', 'analytics', 'insight', 'metric', 'dashboard', 'chart', 'kpi'],
                'epic': {
                    'title': 'Analytics & Reporting',
                    'description': 'Provide insights via dashboards, reports, and exports.'
                }
            },
            'collaboration': {
                'keywords': ['collaborate', 'team', 'share', 'comment', 'mention', 'assign'],
                'epic': {
                    'title': 'Collaboration',
                    'description': 'Enable teams to work together with sharing, commenting, and assignments.'
                }
            },
            'payments': {
                'keywords': ['payment', 'billing', 'checkout', 'subscription', 'invoice', 'stripe', 'paypal', 'pricing'],
                'epic': {
                    'title': 'Payments & Billing',
                    'description': 'Accept payments, manage billing, and handle subscriptions.'
                }
            },
            'security': {
                'keywords': ['secure', 'security', 'privacy', 'encrypt', 'gdpr', 'permission', 'role', 'rbac', 'compliance'],
                'epic': {
                    'title': 'Security & Compliance',
                    'description': 'Protect data, manage permissions, and meet compliance requirements.'
                }
            },
            'integration': {
                'keywords': ['integrate', 'integration', 'api', 'webhook', 'zapier', 'sync', 'import', 'export'],
                'epic': {
                    'title': 'Integrations & APIs',
                    'description': 'Connect with external systems via APIs and webhooks.'
                }
            },
            'performance': {
                'keywords': ['performance', 'fast', 'scalable', 'latency', 'optimize', 'speed'],
                'epic': {
                    'title': 'Performance & Scalability',
                    'description': 'Ensure the system is fast and scales with usage.'
                }
            },
            'mobile': {
                'keywords': ['mobile', 'ios', 'android', 'responsive', 'app'],
                'epic': {
                    'title': 'Mobile & Responsive',
                    'description': 'Deliver a great experience on mobile devices.'
                }
            },
            'i18n': {
                'keywords': ['i18n', 'internationalization', 'localization', 'language', 'translate', 'locale'],
                'epic': {
                    'title': 'Internationalization',
                    'description': 'Support multiple languages and locales.'
                }
            },
            'a11y': {
                'keywords': ['accessibility', 'a11y', 'wcag', 'screen reader', 'contrast', 'keyboard'],
                'epic': {
                    'title': 'Accessibility',
                    'description': 'Comply with accessibility standards for all users.'
                }
            }
        }

        # Candidate domain nouns for resource guessing
        self.domain_nouns = [
            'task', 'tasks', 'project', 'projects', 'note', 'notes', 'order', 'orders', 'product', 'products', 'invoice', 'invoices',
            'customer', 'customers', 'message', 'messages', 'post', 'posts', 'file', 'files', 'document', 'documents',
            'event', 'events', 'booking', 'bookings', 'ticket', 'tickets', 'issue', 'issues', 'bug', 'bugs', 'feature', 'features',
            'article', 'articles', 'listing', 'listings', 'appointment', 'appointments', 'lead', 'leads', 'contact', 'contacts',
            'expense', 'expenses', 'recipe', 'recipes', 'playlist', 'playlists', 'workout', 'workouts', 'goal', 'goals', 'habit', 'habits',
            'image', 'images', 'video', 'videos', 'record', 'records', 'asset', 'assets', 'item', 'items'
        ]

        # Default resource fallback
        self.default_resource = 'items'

    def generate(self, idea: str, context: str = '') -> dict:
        created_at = datetime.utcnow().isoformat() + 'Z'
        resource = self._guess_resource(idea)
        features = self._detect_features(idea)

        if not features:
            features = ['content']  # ensure at least core content epic

        epics = []
        stories = []
        gherkin_features = []

        for idx, feature in enumerate(features, start=1):
            epic_id = _uid('epic')
            epic_meta = self.catalog.get(feature, {}).get('epic', {})
            epic_title = epic_meta.get('title', feature.title())
            epic_desc = epic_meta.get('description', f'Epic for {feature}.')
            priority = self._priority_for_index(idx)

            epic = {
                'id': epic_id,
                'title': epic_title,
                'description': epic_desc,
                'priority': priority,
                'created_at': created_at
            }
            epics.append(epic)

            epic_stories = self._stories_for_feature(feature, resource, epic_id)
            stories.extend(epic_stories)

            gherkin_features.append(self._gherkin_for_epic(epic, epic_stories))

        # Flatten acceptance tests if needed
        acceptance_tests = []
        for s in stories:
            acceptance_tests.append({
                'story_id': s['id'],
                'title': s['title'],
                'scenarios': s['acceptance_criteria']
            })

        return {
            'idea': idea,
            'context': context,
            'resource': resource,
            'epics': epics,
            'stories': stories,
            'acceptance_tests': acceptance_tests,
            'gherkin': '\n\n'.join(gherkin_features)
        }

    def _priority_for_index(self, idx: int) -> str:
        if idx == 1:
            return 'P1'
        if idx in (2, 3):
            return 'P2'
        return 'P3'

    def _detect_features(self, text: str):
        text_low = text.lower()
        found = []
        for feat, meta in self.catalog.items():
            for kw in meta['keywords']:
                if kw in text_low:
                    found.append(feat)
                    break
        # Always include 'security' if sensitive words occur
        sensitive = any(w in text_low for w in ['payment', 'billing', 'health', 'medical', 'privacy', 'pii', 'gdpr'])
        if sensitive and 'security' not in found:
            found.append('security')
        # Deduplicate while preserving order
        seen = set()
        result = []
        for f in found:
            if f not in seen:
                result.append(f)
                seen.add(f)
        return result

    def _guess_resource(self, text: str) -> str:
        if not text:
            return self.default_resource
        tlow = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        words = [w for w in tlow.split() if len(w) > 2]
        candidates = [w for w in words if w in self.domain_nouns]
        if candidates:
            counts = Counter(candidates)
            best = counts.most_common(1)[0][0]
            # singularize naive
            if best.endswith('s') and best[:-1] in self.domain_nouns:
                best = best[:-1]
            return best if best else self.default_resource
        # Try verb-following pattern
        m = re.search(r'(manage|create|track|organize|schedule|share|sell|buy|order|assign|plan|collect|curate)\s+(\w+)', tlow)
        if m:
            word = m.group(2)
            return word if word else self.default_resource
        return self.default_resource

    def _stories_for_feature(self, feature: str, resource: str, epic_id: str):
        gens = {
            'authentication': self._stories_auth,
            'content': self._stories_content,
            'search': self._stories_search,
            'notifications': self._stories_notifications,
            'reporting': self._stories_reporting,
            'collaboration': self._stories_collaboration,
            'payments': self._stories_payments,
            'security': self._stories_security,
            'integration': self._stories_integration,
            'performance': self._stories_performance,
            'mobile': self._stories_mobile,
            'i18n': self._stories_i18n,
            'a11y': self._stories_a11y,
        }
        fn = gens.get(feature, self._stories_content)
        return fn(resource, epic_id)

    def _mk_story(self, epic_id: str, role: str, want: str, so_that: str, acceptance_criteria):
        story_id = _uid('story')
        title = f"{role.title()} can {want}"
        return {
            'id': story_id,
            'epic_id': epic_id,
            'title': title,
            'role': role,
            'description': f"As a {role}, I want to {want} so that {so_that}.",
            'priority': 'P2',
            'acceptance_criteria': acceptance_criteria
        }

    def _stories_auth(self, resource: str, epic_id: str):
        stories = []
        stories.append(self._mk_story(
            epic_id, 'visitor', 'sign up with email and password', 'I can create an account', [
                'Given I am on the sign-up page, When I submit a valid email and strong password, Then my account is created and I am signed in',
                'Given my email is already registered, When I try to sign up again, Then I see an error about existing account',
                'Given I use a weak password, When I submit the form, Then I see guidance to strengthen the password'
            ]
        ))
        stories.append(self._mk_story(
            epic_id, 'user', 'sign in to my account', 'I can access my data securely', [
                'Given I have an account, When I enter correct credentials, Then I am signed in and redirected to my dashboard',
                'Given I enter invalid credentials, When I attempt to sign in, Then I see an error and remain on the sign-in page',
                'Given I enabled 2FA, When I sign in, Then I must enter a valid one-time code'
            ]
        ))
        stories.append(self._mk_story(
            epic_id, 'user', 'reset my password', 'I can recover access if I forget it', [
                'Given I forgot my password, When I request a reset, Then I receive a secure reset link via email',
                'Given I follow the reset link, When I set a new strong password, Then I can sign in with the new password',
                'Given a reset link is expired, When I try to use it, Then I am prompted to request a new link'
            ]
        ))
        return stories

    def _stories_content(self, resource: str, epic_id: str):
        res_plural = resource if resource.endswith('s') else resource + 's'
        stories = []
        stories.append(self._mk_story(
            epic_id, 'user', f'create new {resource}', f'I can add {res_plural} to the system', [
                f'Given I am on the create {resource} form, When I provide valid required fields, Then a new {resource} is saved',
                f'Given required fields are missing, When I submit the form, Then I see validation errors for the {resource}',
                f'Given creation succeeds, When I save, Then I am redirected to the {resource} detail view'
            ]
        ))
        stories.append(self._mk_story(
            epic_id, 'user', f'view a list of {res_plural}', f'I can browse existing {res_plural}', [
                f'Given there are multiple {res_plural}, When I open the list page, Then I see paginated {res_plural} with key fields',
                f'Given there are more than a page of {res_plural}, When I navigate pages, Then I can access all {res_plural}',
                f'Given there are no {res_plural}, When I open the list, Then I see an empty state with a call to action to create one'
            ]
        ))
        stories.append(self._mk_story(
            epic_id, 'user', f'edit an existing {resource}', f'I can correct or update information on {res_plural}', [
                f'Given I am on the {resource} detail, When I click edit and submit valid changes, Then the {resource} is updated',
                f'Given I attempt invalid changes, When I save, Then I see validation errors and no changes are persisted',
                f'Given I cancel editing, When I return, Then no changes are applied'
            ]
        ))
        stories.append(self._mk_story(
            epic_id, 'user', f'delete a {resource}', f'I can remove {res_plural} that are no longer needed', [
                f'Given I view a {resource}, When I confirm deletion, Then the {resource} is removed and I see a success message',
                f'Given I start deletion, When I cancel the confirmation, Then the {resource} remains',
                f'Given a {resource} is linked to other data, When I attempt deletion, Then I see a warning or the action is blocked with guidance'
            ]
        ))
        return stories

    def _stories_search(self, resource: str, epic_id: str):
        res_plural = resource if resource.endswith('s') else resource + 's'
        return [
            self._mk_story(epic_id, 'user', f'search {res_plural} by keyword', f'I can quickly find specific {res_plural}', [
                f'Given there are {res_plural}, When I enter a keyword, Then results show matching {res_plural} ranked by relevance',
                f'Given no {res_plural} match, When I search, Then I see a clear empty state and suggestions',
                f'Given I search repeatedly, When I open the search box, Then I see recent queries'
            ]),
            self._mk_story(epic_id, 'user', f'filter {res_plural} by common attributes', f'I can narrow down results', [
                f'Given filters are available, When I apply multiple filters, Then the {res_plural} list updates to reflect selections',
                f'Given filters are active, When I clear them, Then I see the full {res_plural} list',
                f'Given many filters, When I refresh the page, Then my filter state persists'
            ])
        ]

    def _stories_notifications(self, resource: str, epic_id: str):
        res_plural = resource if resource.endswith('s') else resource + 's'
        return [
            self._mk_story(epic_id, 'user', f'receive notifications about {res_plural}', f'I am informed about important changes', [
                f'Given a notable event happens to my {resource}, When notifications are enabled, Then I receive a notification',
                f'Given quiet hours are set, When an event occurs, Then notifications are deferred until quiet hours end',
                f'Given I disable notifications, When an event occurs, Then I do not receive notifications'
            ]),
            self._mk_story(epic_id, 'user', 'configure notification preferences', 'I control when and how I am notified', [
                'Given I am on preferences, When I select channels (email, push), Then only those channels are used',
                'Given I set frequency to daily digest, When many events occur, Then I receive a single daily summary',
                'Given I opt out of marketing, When notifications are sent, Then I only receive transactional messages'
            ])
        ]

    def _stories_reporting(self, resource: str, epic_id: str):
        res_plural = resource if resource.endswith('s') else resource + 's'
        return [
            self._mk_story(epic_id, 'user', f'view a dashboard of {res_plural} metrics', 'I can monitor performance at a glance', [
                'Given I have data, When I open the dashboard, Then I see key metrics and charts',
                'Given I change the date range, When I apply it, Then charts update accordingly',
                'Given I have no data, When I open the dashboard, Then I see helpful getting-started tips'
            ]),
            self._mk_story(epic_id, 'user', 'export reports to CSV', 'I can analyze data outside the app', [
                'Given a report is available, When I click export, Then a CSV file downloads with correct headers',
                'Given filters are applied, When I export, Then only filtered data is included',
                'Given the dataset is large, When I export, Then the system generates the file asynchronously and notifies me when ready'
            ])
        ]

    def _stories_collaboration(self, resource: str, epic_id: str):
        res_plural = resource if resource.endswith('s') else resource + 's'
        return [
            self._mk_story(epic_id, 'user', f'invite teammates to collaborate on {res_plural}', 'we can work together', [
                'Given I have permission, When I invite a teammate via email, Then they receive an invitation to join',
                'Given an invite is pending, When I resend it, Then a new email is sent and the expiry extends',
                'Given I revoke an invite, When the recipient clicks it, Then access is denied'
            ]),
            self._mk_story(epic_id, 'user', f'comment on a {resource}', 'we can discuss context in one place', [
                f'Given I view a {resource}, When I post a comment, Then it appears with my name and timestamp',
                'Given I mention a teammate using @name, When I submit, Then they are notified',
                'Given I lack permission, When I try to comment, Then I see an authorization error'
            ])
        ]

    def _stories_payments(self, resource: str, epic_id: str):
        return [
            self._mk_story(epic_id, 'customer', 'add a payment method', 'I can pay securely', [
                'Given I am on the billing page, When I enter valid card details, Then the card is tokenized and saved',
                'Given the card is invalid, When I submit, Then I see a clear error and nothing is saved',
                'Given I have a default card, When I add a new one, Then I can set it as the default'
            ]),
            self._mk_story(epic_id, 'customer', 'complete checkout', 'I can purchase without friction', [
                'Given I have items in cart, When I confirm payment, Then an order is created and I see a receipt',
                'Given payment fails, When I retry, Then I can attempt again or choose another method',
                'Given taxes apply, When I checkout, Then totals include correct taxes and fees'
            ])
        ]

    def _stories_security(self, resource: str, epic_id: str):
        return [
            self._mk_story(epic_id, 'admin', 'manage roles and permissions', 'I can control access', [
                'Given roles exist, When I assign a role to a user, Then their permissions update immediately',
                'Given a user lacks permission, When they access restricted pages, Then access is denied and audited',
                'Given I change a role, When I save, Then the change is recorded in the audit log'
            ]),
            self._mk_story(epic_id, 'user', 'enable two-factor authentication', 'I can protect my account', [
                'Given I scan a QR code, When I enter a valid TOTP, Then 2FA is enabled for my account',
                'Given I lose my device, When I use backup codes, Then I can still sign in securely',
                'Given 2FA is enabled, When I sign in, Then the system requires a valid one-time code'
            ])
        ]

    def _stories_integration(self, resource: str, epic_id: str):
        return [
            self._mk_story(epic_id, 'admin', 'configure webhooks', 'external systems can react to events', [
                'Given I add a webhook URL, When events occur, Then the system POSTs event payloads to the URL',
                'Given a webhook fails repeatedly, When retries exceed limits, Then the webhook is paused and I am notified',
                'Given I view delivery logs, When I filter by status, Then I can troubleshoot failures'
            ]),
            self._mk_story(epic_id, 'developer', 'create and rotate API keys', 'I can authenticate API requests', [
                'Given I create an API key, When I copy it, Then it is only shown once for security',
                'Given a key is compromised, When I revoke it, Then further requests with that key are rejected',
                'Given keys have scopes, When I assign least privilege, Then APIs enforce scope checks'
            ])
        ]

    def _stories_performance(self, resource: str, epic_id: str):
        res_plural = resource if resource.endswith('s') else resource + 's'
        return [
            self._mk_story(epic_id, 'user', f'load {res_plural} list within 2 seconds', 'the app feels responsive', [
                f'Given there are many {res_plural}, When I open the list, Then the first contentful paint is under 2 seconds on a 3G network',
                'Given images are present, When they load, Then they are lazy-loaded below the fold',
                'Given repeated visits, When I return, Then cached assets are reused'
            ]),
            self._mk_story(epic_id, 'user', 'paginate long lists', 'I can navigate large datasets efficiently', [
                'Given there are thousands of records, When I view the list, Then results are paginated by default',
                'Given I change page size, When I apply it, Then the list updates and my preference persists',
                'Given I scroll, When I reach the end, Then the next page loads seamlessly (infinite scroll or controls)'
            ])
        ]

    def _stories_mobile(self, resource: str, epic_id: str):
        res_plural = resource if resource.endswith('s') else resource + 's'
        return [
            self._mk_story(epic_id, 'user', 'use the app comfortably on mobile', 'I can complete tasks on small screens', [
                'Given I am on a phone, When I open the app, Then layouts are responsive and touch targets are accessible',
                'Given long forms, When I input data, Then the keyboard does not obscure fields and the viewport scrolls appropriately',
                'Given images and tables, When I view them, Then they adapt to screen size without horizontal scrolling'
            ]),
            self._mk_story(epic_id, 'user', f'access {res_plural} offline (read-only)', 'I can reference content without connectivity', [
                'Given I visited a page before, When I go offline, Then I can still view cached content',
                'Given I am offline, When I try to modify data, Then I see an informative message and no changes are made',
                'Given connectivity is restored, When I retry, Then content updates as expected'
            ])
        ]

    def _stories_i18n(self, resource: str, epic_id: str):
        return [
            self._mk_story(epic_id, 'user', 'switch the interface language', 'I can use the app in my preferred language', [
                'Given multiple languages are supported, When I select a language, Then UI texts update immediately',
                'Given I return later, When I log in, Then my language preference persists',
                'Given content has translations, When I switch languages, Then localized content is displayed'
            ])
        ]

    def _stories_a11y(self, resource: str, epic_id: str):
        return [
            self._mk_story(epic_id, 'user', 'navigate using only the keyboard', 'the app is accessible without a mouse', [
                'Given I focus elements, When I press Tab/Shift+Tab, Then focus order is logical and visible',
                'Given interactive controls, When I use keyboard shortcuts, Then all actions are operable',
                'Given form inputs, When I submit, Then errors are announced to assistive technologies'
            ]),
            self._mk_story(epic_id, 'user', 'use the app with a screen reader', 'I can understand and operate the interface', [
                'Given I enable a screen reader, When I navigate, Then UI elements have appropriate roles, names, and states',
                'Given images convey meaning, When I encounter them, Then they include descriptive alt text',
                'Given color is used to convey meaning, When I view content, Then there are redundant non-color indicators'
            ])
        ]

    def _gherkin_for_epic(self, epic: dict, stories: list) -> str:
        lines = [f"Feature: {epic['title']}", f"  # {epic['description']}"]
        for s in stories:
            lines.append(f"\n  Scenario: {s['title']}")
            for ac in s['acceptance_criteria']:
                # Split Gherkin-ish text into Given/When/Then lines if possible
                g = re.split(r',?\s*When\s+', ac, flags=re.IGNORECASE)
                if len(g) == 2:
                    given_part, rest = g
                    given_part = given_part.strip()
                    lines.append(f"    {self._prefix_line(given_part, 'Given')}")
                    w = re.split(r',?\s*Then\s+', rest, flags=re.IGNORECASE)
                    if len(w) == 2:
                        when_part, then_part = w
                        lines.append(f"    When {when_part.strip()}")
                        lines.append(f"    Then {then_part.strip()}")
                        continue
                # Fallback single-line
                lines.append(f"    # {ac}")
        return '\n'.join(lines)

    def _prefix_line(self, text: str, default_prefix: str) -> str:
        t = text.strip()
        if re.match(r'^(Given|When|Then|And)\b', t, flags=re.IGNORECASE):
            return t
        return f"{default_prefix} {t}"

