# Outproxy

This proxy servers as an outgoing proxy that denies all requests to local or private ip addresses or hosts (e.g. `127.0.0.1`, `10.*.*.*`, `localhost`)

## Deployment: 
Run this proxy with:
```cmd
docker build -t outproxy .
docker run --read-only --name proxy --rm outproxy
```

Per default it listens on port `8080`.