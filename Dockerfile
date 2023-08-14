FROM hdm-backend:v6
WORKDIR /workspace/power_model_system
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["./scripts/start.sh"]
