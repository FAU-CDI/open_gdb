package outproxy

import (
	"fmt"
	"log"
	"math/rand"
	"net"
	"net/http"
	"time"

	"github.com/elazarl/goproxy"
)

type Options struct {
	Filter  func(ip net.IP) bool                // The filter function for IP addresses. Should return true when IP is supposed to be blocked.
	Lookup  func(host string) ([]net.IP, error) // DNS lookup function.
	Timeout time.Duration                       // Dial up timeout.
}

func MakeProxy(options Options) *goproxy.ProxyHttpServer {
	proxy := goproxy.NewProxyHttpServer()
	proxy.Verbose = true

	proxy.Tr = &http.Transport{
		Dial: func(network, addr string) (net.Conn, error) {
			log.Println("Dial", addr)
			host, port, _ := net.SplitHostPort(addr)

			ips, err := options.Lookup(host)
			if err != nil {
				return nil, err
			}

			ip, err := filterIp(ips, options.Filter)
			if err != nil {
				return nil, err
			}

			return net.DialTimeout(network, net.JoinHostPort(ip.String(), port), options.Timeout)
		},
	}
	return proxy
}

// filterIp filters the given IP addresses with the filter function and randomly returns one that passes the filter.
// ips is the list of IPs to filter.
// filter is the filter function and should return true if the IP should be blocked.
func filterIp(ips []net.IP, filter func(ip net.IP) bool) (net.IP, error) {
	// Random shuffle to redirect requests to every valid IP.
	rand.Shuffle(len(ips), func(i, j int) { ips[i], ips[j] = ips[j], ips[i] })
	for _, ip := range ips {
		if ip != nil && !filter(ip) {
			return ip, nil
		}
	}
	return nil, restrictedError
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
