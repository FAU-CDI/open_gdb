package outproxy

import (
	"fmt"
	"math/rand"
	"net"
	"net/http"
	"time"

	"github.com/elazarl/goproxy"
)

// Options describes options for creating an outproxy instance.
type Options struct {
	// Filter is a non-nil function to filter ip addresses to be permitted.
	Filter func(ip net.IP) bool

	// Lookup is used to resolve a hostname into an ip address.
	// When nil, uses [net.LookupIP].
	Lookup func(host string) ([]net.IP, error)

	// Timeout is the default timeout to use when attempting to dial a specific ip address.
	// NOTE: If a host resolves to multiple ip addresses, the timeout is applied to each.
	Timeout time.Duration
}

// resolve uses the Lookup function, or defaults to [net.LookupIP] when nil.
func (options Options) resolve(host string) ([]net.IP, error) {
	if options.Lookup == nil {
		return net.LookupIP(host)
	}
	return options.Lookup(host)
}

// MakeProxy creates a new proxy based on options
func MakeProxy(options Options) *goproxy.ProxyHttpServer {
	proxy := goproxy.NewProxyHttpServer()
	proxy.Verbose = true

	proxy.Tr = &http.Transport{
		Dial: func(network, addr string) (net.Conn, error) {
			// resolve into host and port
			host, port, _ := net.SplitHostPort(addr)

			// find all the ips
			ips, err := options.resolve(host)
			if err != nil {
				return nil, err
			}

			// filter the ips to only contain the allowed ones
			n := 0
			for _, ip := range ips {
				if options.Filter(ip) {
					continue
				}
				ips[n] = ip
				n++
			}
			ips = ips[:n]

			// no ips allowed, or nothing resolved
			if n == 0 {
				return nil, restrictedError
			}

			// shuffle the ips around
			rand.Shuffle(len(ips), func(i, j int) { ips[i], ips[j] = ips[j], ips[i] })

			// try to dial each of the ips
			for _, ip := range ips {
				var conn net.Conn

				// if we successfully dial, return the connection
				conn, err = net.DialTimeout(network, net.JoinHostPort(ip.String(), port), options.Timeout)
				if err == nil {
					return conn, err
				}
			}

			// return the last error
			return nil, err
		},
	}
	return proxy
}

// IsLocal checks if the given IP is a local IP address and returns true when it is, false otherwise.
func IsLocal(ip net.IP) bool {
	return net.IP.IsInterfaceLocalMulticast(ip) ||
		net.IP.IsLinkLocalMulticast(ip) ||
		net.IP.IsLinkLocalUnicast(ip) ||
		net.IP.IsLoopback(ip) ||
		net.IP.IsMulticast(ip) ||
		net.IP.IsUnspecified(ip) ||
		net.IP.IsPrivate(ip)
}

// IsLocalOrIPv6 checks if the given IP is a local IP address or a IPv6 address and returns true when it is, false otherwise.
func IsLocalOrIPv6(ip net.IP) bool {
	// Return true if IPv6
	if ip.To4() == nil {
		return true
	}
	return IsLocal(ip)
}

var restrictedError error

func init() {
	// Initialize error once.
	restrictedError = fmt.Errorf("no unrestricted ip address found")
}
