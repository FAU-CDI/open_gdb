package main

import (
	"flag"
	"log"
	"net"
	"net/http"
	"outproxy"
	"time"
)

func main() {
	options := outproxy.Options{
		Filter:  outproxy.IsLocal,
		Lookup:  net.LookupIP,
		Timeout: timeout,
	}
	proxy := outproxy.MakeProxy(options)

	listener, err := net.Listen("tcp", addr)
	if err != nil {
		log.Fatal(err)
		return
	}
	log.Printf("listening on %s", addr)
	log.Fatal(http.Serve(listener, proxy))
}

var addr string
var timeout time.Duration

func init() {
	defer flag.Parse()

	flag.StringVar(&addr, "addr", ":8080", "address to listen on")
	flag.DurationVar(&timeout, "timeout", time.Second, "timeout for net dial")
}
