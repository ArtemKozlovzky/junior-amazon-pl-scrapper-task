## A) Curl-vs-browser header diff

Curl or requests sends only basic set of headers like:

simple user-agent, accept and accept-encoding

While browser sends:

full browser user-agent, accept, accept-encoding, accept-language, Sec-Fetch-*,
Sec-CH-UA-*, cookies and referer 

It is important to know because anti-bot detection systems check if all the 
headers are provided, their order and values

## B) Anatomy of a request, Headers, TLS/JA3 fingerprinting

### HTTP request consists of:
- Method(GET, POST, PUT, DELETE)
- URL(https://www.amazon.pl/s?k=coffee&page=2)
- Headers(User-Agent, accept, accept-language etc.)
- Cookies(User session data)
- Body

### Headers
Headers are simply an additional data for server or client that 
helps to figure out how to properly process a request or answer

### TLS/JA3 fingerprinting
TLS fingerprinting is the way for server to identify 
client software using open ClientHello during TLS Handshake

JA3 takes TLS version, ciper suites, extensions, supporter
groups and point formats from open ClientHello and creates a 
JA3-hash that is compared to known hashes of browsers, 
curl, malware and so on

## C) The bot-detection vendor marker table


| **Vendor** | **Cookies** | **Headers** | **JS / block signature** |
|---|---|---|---|
| Akamai Bot Manager | `_abck`; `bm_sz`; `ak_bmsc` | `Server: AkamaiGHost` | Inlined ~512 KB `sensor.js`; блокировка с телом "Pardon Our Interruption" на 412 |
| Cloudflare Bot Management / Turnstile | `cf_clearance`; `__cf_bm` | `Server: cloudflare`; `cf-ray`; `cf-mitigated: challenge` | `/cdn-cgi/challenge-platform/assets`; Turnstile widget `challenges.cloudflare.com`; Error 1015 при rate limit |
| DataDome | `datadome`; `dd_cookie_test_*` | `x-datadome-cid`; `x-dd-b` | JS `/js/datadome.js`; WASM `boring_challenge`; CAPTCHA `geo.captcha-delivery.com` |
| PerimeterX (HUMAN) | `_px3`; `_pxhd`; `_pxde`; `_pxvid` | `x-px-*` family | JS `/init.js` с `client.px-cdn.net`; Human Challenge press-and-hold widget |
| Kasada | `x-kpsdk-ct`; `x-kpsdk-cd` | `x-kpsdk-*` response headers | Полиморфный `ips.js` (переименовывается); silent 403 / 429 без UI |
| F5 Shape Security | `reese84`; `TS*` | Custom `TS*` set-cookies | Собственный JS VM bytecode; `$rsc=` URL params; токены ротируются каждую минуту |

## D) The two tls.peet.ws JSON responses

### requests

    "tls_version_record": "771",
    "tls_version_negotiated": "772",
    "ja3": "771,4866-4867-4865-49196-49200-49195-49199-52393-52392-49188-49192-49187-49191-159-158-107-103-255,0-11-10-16-22-23-49-13-43-45-51-21,29-23-30-25-24-256-257-258-259-260,0-1-2",
    "ja3_hash": "a48c0d5f95b1ef98f560f324fd275da1",
    "ja4": "t13d1812h1_85036bcba153_375ca2c5e164",
    "ja4_r": "t13d1812h1_0067,006b,009e,009f,00ff,1301,1302,1303,c023,c024,c027,c028,c02b,c02c,c02f,c030,cca8,cca9_000a,000b,000d,0016,0017,002b,002d,0031,0033_0403,0503,0603,0807,0808,0809,080a,080b,0804,0805,0806,0401,0501,0601,0303,0301,0302,0402,0502,0602",
    "peetprint": "772-771|1.1|29-23-30-25-24-256-257-258-259-260|1027-1283-1539-2055-2056-2057-2058-2059-2052-2053-2054-1025-1281-1537-771-769-770-1026-1282-1538|1||4866-4867-4865-49196-49200-49195-49199-52393-52392-49188-49192-49187-49191-159-158-107-103-255|0-10-11-13-16-21-22-23-43-45-49-51",
    "peetprint_hash": "76017c4a71b7a055fb2a9a5f70f05112",
    "client_random": "a7b848c6765f62284d1fd66f08293e522a06d09cbafac6e5d3b00e3449041d16",
    "session_id": "7ce239071aee72061983b8a7afe635211239030f3252e64c10cf94357f5dab15"

    "http1": 
      "headers": 
        "Host: tls.peet.ws",
        "User-Agent: python-requests/2.34.2",
        "Accept-Encoding: gzip, deflate",
        "Accept: */*",
        "Connection: keep-alive"

### curl_cffi

    "tls_version_record": "771",
    "tls_version_negotiated": "772",
    "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,16-65281-27-51-43-23-11-45-65037-0-35-5-13-18-10-17513,25497-29-23-24,0",
    "ja3_hash": "2f5f9beb7479610abcf0c1879bfce7d7",
    "ja4": "t13d1516h2_8daaf6152771_02713d6af862",
    "ja4_r": "t13d1516h2_002f,0035,009c,009d,1301,1302,1303,c013,c014,c02b,c02c,c02f,c030,cca8,cca9_0005,000a,000b,000d,0012,0017,001b,0023,002b,002d,0033,4469,fe0d,ff01_0403,0804,0401,0503,0805,0501,0806,0601",
    "peetprint": "GREASE-772-771|2-1.1|GREASE-25497-29-23-24|1027-2052-1025-1283-2053-1281-2054-1537|1|2|GREASE-4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53|0-10-11-13-16-17513-18-23-27-35-43-45-5-51-65037-65281-GREASE-GREASE",
    "peetprint_hash": "b8ce945a4d9a7a9b5b6132e3658fe033",
    "client_random": "1b37fc4379a35853bb675795e91e81a581e5c86aabf57bd058d19fd464447624",
    "session_id": "f31dcd1d61aa2551abdc9a92634bdb1068a4ddae96fcbe73e4018077f572d735"
  
    "http2": {
    "akamai_fingerprint": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
    "akamai_fingerprint_hash": "52d84b11737d980aef856699f885ca86",
    "sent_frames": [
      {
        "frame_type": "SETTINGS",
        "length": 24,
        "settings": [
          "HEADER_TABLE_SIZE = 65536",
          "ENABLE_PUSH = 0",
          "INITIAL_WINDOW_SIZE = 6291456",
          "MAX_HEADER_LIST_SIZE = 262144"
        ]
      },
      {
        "frame_type": "WINDOW_UPDATE",
        "length": 4,
        "increment": 15663105
      },
      {
        "frame_type": "HEADERS",
        "stream_id": 1,
        "length": 462,
        "headers": [
          ":method: GET",
          ":authority: tls.peet.ws",
          ":scheme: https",
          ":path: /api/all",
          "sec-ch-ua: \\\"Chromium\\\";v=\\\"124\\\", \\\"Google Chrome\\\";v=\\\"124\\\", \\\"Not-A.Brand\\\";v=\\\"99\\",
          "sec-ch-ua-mobile: ?0",
          "sec-ch-ua-platform: \\\"macOS\\",
          "upgrade-insecure-requests: 1",
          "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
          "accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
          "sec-fetch-site: none",
          "sec-fetch-mode: navigate",
          "sec-fetch-user: ?1",
          "sec-fetch-dest: document",
          "accept-encoding: gzip, deflate, br, zstd",
          "accept-language: en-US,en;q=0.9",
          "priority: u=0, i"
        ],
        "flags": [
          "EndStream (0x1)",
          "EndHeaders (0x4)",
          "Priority (0x20)"
        ],
        "priority": {
          "weight": 256,
          "depends_on": 0,
          "exclusive": 1


## Why requests is not enough?

Requests allows you to fetch a page, but its TLS and HTTP fingerprints 
are easily detected by anti-bot systems. curl_cffi makes the network 
fingerprint closely resemble that of a genuine Chrome browser, significantly 
reducing the likelihood of being blocked. However, it is not a substitute 
for a full-fledged browser and cannot execute JavaScript.