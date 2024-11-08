# build the user permission server
FROM alpine AS permission

# Create www-data
RUN set -x ; \
  addgroup -g 82 -S www-data ; \
  adduser -u 82 -D -S -G www-data www-data && exit 0 ; exit 1

FROM golang:1.23 AS build

WORKDIR /app
COPY . .
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o outproxy ./cmd/outproxy

FROM scratch
WORKDIR /

# add the user
COPY --from=permission /etc/passwd /etc/passwd
COPY --from=permission /etc/group /etc/group

COPY --from=build /app/outproxy /outproxy
EXPOSE 8080
USER www-data:www-data
CMD ["/outproxy"]