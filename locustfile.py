from locust import HttpUser, task, between


class LoginUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def login(self):
        self.client.post(
            "/login",
            data={
                "email": "test@gmail.com",
                "password": "12345678"
            },
            name="/login"
        )