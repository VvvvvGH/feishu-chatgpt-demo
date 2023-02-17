docker build -t robot-gpt .
docker run --name gpt --env-file .env -p 3000:3000 -it robot-gpt
