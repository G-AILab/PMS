#!/bin/sh
source /root/.virtualenvs/celery_virtual/bin/activate
celery -A flask_app.celery_tasks.tasks worker -l info -c 80 -n worker0 --heartbeat-interval=30