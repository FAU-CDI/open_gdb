package main

import (
	"flag"
	"log"
	"net"
	"net/http"
	"os"
	"outproxy"
	"time"
)

func main() {
	options := outproxy.Options{
		Filter:  outproxy.IsLocalOrIPv6,
		Lookup:  net.LookupIP,
		Timeout: timeout,
	}

	// if v6 is enabled, skip filtering v6
	if enableV6 {
		options.Filter = outproxy.IsLocal
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
var enableV6 bool
var timeout time.Duration

func init() {
	defer flag.Parse()

	flag.StringVar(&addr, "addr", ":8080", "address to listen on")
	flag.BoolVar(&enableV6, "ipv6", os.Getenv("ENABLE_IPV6") != "", "enable ipv6 support (set ENABLE_IPV6 environment variable to enable)")
	flag.DurationVar(&timeout, "timeout", time.Second, "timeout for net dial")
}
