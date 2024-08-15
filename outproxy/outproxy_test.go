package outproxy_test

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"outproxy"
	"testing"
	"time"
)

func TestProxy(t *testing.T) {

	endpoint := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		io.WriteString(w, "ok")
	}))
	defer endpoint.Close()

	u, err := url.Parse(endpoint.URL)
	if err != nil {
		t.Fatalf("failed to parse endpoint URL: %v", err)
	}

	ip := net.ParseIP(u.Hostname())
	if ip == nil {
		t.Fatalf("failed to parse endpoint IP")
	}

	filterFunctionCalled := false

	proxy := outproxy.MakeProxy(outproxy.Options{
		Filter: func(ip net.IP) bool {
			filterFunctionCalled = true
			return false
		},
		Lookup: func(host string) ([]net.IP, error) {
			if host != "example.com" {
				t.Fatalf("wrong domain requested")
			}
			return []net.IP{ip}, nil
		},
		Timeout: time.Second,
	})

	proxyserver := httptest.NewServer(proxy)
	defer proxyserver.Close()

	purl, err := url.Parse(proxyserver.URL)
	if err != nil {
		t.Fatalf("failed to create proxy ")
	}

	client := http.Client{
		Transport: &http.Transport{Proxy: http.ProxyURL(purl)},
	}
	// t.helper
	res, err := client.Get(fmt.Sprintf("http://example.com:%v/", u.Port()))
	if err != nil {
		t.Errorf("failed to get url: %v", err)
	}
	defer res.Body.Close()

	if res.StatusCode != http.StatusOK {
		t.Errorf("wanted status ok")
	}

	if !filterFunctionCalled {
		t.Errorf("something went wrong")
	}

}
