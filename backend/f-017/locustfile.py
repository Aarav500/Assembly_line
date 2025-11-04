from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def index(self):
        self.client.get('/')

    @task(2)
    def health(self):
        self.client.get('/health')

    @task(1)
    def get_user(self):
        self.client.get('/api/users/123')

    @task(1)
    def slow_endpoint(self):
        self.client.get('/api/slow')
