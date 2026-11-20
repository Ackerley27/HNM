# Monitoring collection

The backend runs one asynchronous collection worker when the application
starts. It never sends configuration changes to network equipment. The
dashboard reports `data_mode` as either `demo` or `live` and filters out the
other mode's records.

## Demo mode

`MONITORING_MODE=demo` is the default. It idempotently creates four departments,
eight example devices, demo hosts, 24 hours of traffic history, sample device
metrics, flow metadata, and a sample offline alert. Documentation-only IP
ranges are used. The dashboard labels the entire view `DEMO DATA`; none of
these records come from hospital equipment.

## Live mode

Set `MONITORING_MODE=live`. Each provider reports its own health. A missing,
unreachable, or invalid source is shown as unavailable; live mode never falls
back to demo values. Credentials belong only in the backend environment or
secret manager and are not written to the database or returned by the API.
Use read-only accounts and HTTPS for remote APIs.

### Zabbix

Set `ZABBIX_API_URL` to the server base URL or the full
`/api_jsonrpc.php` URL, and set `ZABBIX_API_TOKEN` to a read-only API token.
The adapter calls only `host.get` and `item.get`. It reads host/interface
availability and the `system.cpu.util[...]` and
`vm.memory.size[pused]` item keys. It updates only devices already registered
with `source=zabbix` and the matching Zabbix `source_device_id`; it does not
guess equipment types or create devices.

### ntopng

Set `NTOPNG_API_URL`, `NTOPNG_USERNAME`, `NTOPNG_PASSWORD`, and
`NTOPNG_INTERFACE_ID`. The adapter uses HTTP Basic authentication and the
read-only REST v2 interface-data and active-host endpoints. It stores active
host IP/first-seen/last-seen metadata and traffic counter deltas. The first
successful counter read establishes a baseline, so it does not create a
traffic interval until the next sample. Host-list failure is logged while
interface health remains independently checked.

### SNMPv3

Set `SNMPV3_TARGETS` to a JSON array of authorized targets. Each target
requires `ip_address`, `username`, `auth_key`, and `privacy_key`; optional
`port` defaults to 161. The current collector uses SNMPv3 authPriv with
SHA-256 authentication and AES-128 privacy by default; `auth_protocol` can be
set to `SHA1` only for equipment that lacks SHA-256 support. It performs only
a GET for `sysUpTime.0`. Targets are IP addresses, not arbitrary hostnames. A
failed probe is reported as unavailable (not assumed offline). Devices are
matched to the inventory by IP address.

### NetFlow and syslog UDP inputs

Both UDP receivers are disabled by default and bind to loopback by default.
When enabling either receiver, configure its exporter allowlist; startup
validation rejects enabled listeners without an allowlist. Change the bind
host only when the server firewall and network routing have been reviewed.
Ingestion queues are bounded and malformed or unapproved datagrams are
dropped.

The flow listener currently parses NetFlow v5 metadata only: IP addresses,
ports, protocol, timestamps, byte counts, and packet counts. It does not parse
packet payloads. IPFIX and sFlow template parsing are not implemented yet.
The syslog listener reads only the priority header and stores a generic
severity summary; it discards message content.

## Operational limits

`COLLECTOR_INTERVAL_SECONDS` accepts 10–3600 seconds. Database migrations must
be applied before collection starts. If migrations are missing, collection
errors are written to the backend log and retried at the configured interval.
Run a single API process while collection is hosted in the API lifespan; a
multi-worker deployment should move collection into a dedicated worker service.
Collectors and protocol parsers have mocked/unit tests, but no real Zabbix,
ntopng, SNMP, NetFlow exporter, or syslog sender was available for an end-to-end
live integration test.

## Alert evaluation

In live mode, each successful collection cycle also evaluates persisted
measurements. The default aggregate bandwidth threshold is 500 Mbps. Unusual
traffic requires a current per-source/device/interface/direction average to
exceed the corresponding preceding-24-hour average by the configured
multiplier and minimum rate. Offline alerts are created only for registered,
monitoring-enabled devices whose collector reports `offline`; an unavailable
collector does not prove a device is offline. Active alerts are deduplicated,
and traffic-related alerts are resolved only when later measurements confirm
that the threshold is no longer exceeded. When measurements are absent, the
evaluator preserves the existing alert state rather than treating missing data
as recovery. Threshold changes and alert status actions are audit logged.
