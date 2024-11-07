# Outproxy

This proxy servers as an outgoing proxy that denies all requests to local or private ip addresses or hosts (e.g. `127.0.0.1`, `10.*.*.*`, `localhost`)

## Deployment:
Run this proxy with:
```cmd
docker build -t outproxy .
docker run --read-only --name proxy --rm outproxy
```

Per default it listens on port `8080`.

## Configuration:
Since this proxy is designed to be used in a docker context, this proxy by default automatically blocks all requests to IPv6 addresses.
If you want to enable redirecting to IPv6 addresses, set the `ENABLE_IPV6` environment variable, or start the executable with the `--ipv6` flag.