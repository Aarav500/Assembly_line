import multiprocessing

bind = "0.0.0.0:8000"
workers = max(1, multiprocessing.cpu_count() // 2)
threads = 2
timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"

