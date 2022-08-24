#!/usr/bin/env python
# vim:sw=4
"""
# AWS Infra Mgmt

Currently only route53

## Examples

Wiith "dev-xyz.mydomain.com" present at AWS:

dns_create -n myhost.k3s.dev-xyz.mydomain.com -ips=1.2.3.4,1.1.1.1
dns_delete -n myhost.k3s.dev-xyz.mydomain.com
"""

import os
from devapp.app import run_app, FLG, app
from devapp.tools.infra import Actions, Flags, Provider, Api, Prov, fmt, rm
import time
import hmac, hashlib, requests, base64
from operator import setitem
from devapp.tools import cache, write_file

# Droplet list results are cached in tmp/droplets.json. We will read from here if recent.'
# droplet_list_cache_max_age = int(os.environ.get('droplet_list_cache_max_age', 3))


# only route53 action supported, remove all others:
rma = lambda key, f: delattr(Actions, key) if callable(f) else 0
[rma(d, getattr(Actions, d)) for d in dir(Actions) if not d[0] == '_']


def dotted(name, create=True):
    name = name or FLG.name
    if not name.endswith('.'):
        name += '.'
    FLG.name = name
    Prov().assert_sane_name(name, create)
    return name


class Actions(Actions):
    def dns_list(name=None, **kw):
        return Prov().list_simple(name, Prov().dns, lister=zones.get, **kw)

    def domain_list(name=None):
        return Prov().list_simple(name, Prov().domain, lister=get_domains)

    list = dns_list

    class kube_add_cert_manager:
        class version:
            d = '1.9.1'

        class email:
            d = 'me@mydomain.com'

        class zone:
            d = 'mydomain.com'

        def run():
            breakpoint()   # FIXME BREAKPOINT
            v, k = FLG.kube_add_cert_manager_version, Prov().kubectl
            url = f'https://github.com/cert-manager/cert-manager/releases/download/v{v}/cert-manager.yaml'
            k.apply(url)   # creates ns
            _ = {'secret-access-key': Api.secrets['aws_secret']}
            k.add_secret(name='prod-route53-credentials-secret', ns='cert-manager', kv=_)
            email = FLG.kube_add_cert_manager_email
            zone = FLG.kube_add_cert_manager_zone
            t = TCertMgr.format(email=email, zone=zone, id=Api.secrets['aws_key'])
            for tries in range(10):
                if not k.apply(
                    'conf/cert_request.yaml',
                    body=t,
                ):
                    return
                app.info('retrying cert request', attempts=f'{tries}/10')
                time.sleep(1)

    class kube_add_ext_dns:
        class gw_api:
            n = 'Configure GatewayAPI'
            d = False

        class zone:
            d = 'mydomain.com'

        class version:
            d = '0.12.0'

        def run():
            assert FLG.kube_add_ext_dns_gw_api, 'Only GW API Support Supported'
            k, S = Prov().kubectl, Api.secrets
            D = 'external-dns'
            k.add_namespace(D)
            T = TINI.format(key=S['aws_key'], secret=S['aws_secret']).strip()
            k.add_secret(f'{D}-aws', D, {'credentials': T})
            k.apply('conf/ext_dns.yaml', TEXTDNS)
            zone = FLG.kube_add_ext_dns_zone
            version = FLG.kube_add_ext_dns_version
            s = T_EXTDNS_DEPL.format(zone=zone, version=version, user=os.environ['USER'])
            k.apply('conf/ext_dns_depl.yaml', s)

    class dns_create:
        class ips:
            s = 'ips'
            n = 'Adds A record. Set flag name to intended zone (domain must be present) and give a list of ips'
            d = []

        class ttl:
            s = 'ttl'
            d = 120

        class rm:
            s = 'rm'
            n = 'delete any existing zone before creation'
            d = False

        class multi:
            s = 'multi'
            n = 'Provide host::ip1:ip2,host2:ip3 in one go. Ignores name and ips flags. ttl and rm is respected. If rm is set, we safe get roundtrips and just delete before creating when present.'
            d = []

        def run(name=None, ips=None, ttl=None, c=[0], multi=False):
            """we do it all here"""
            if not multi:
                m = FLG.dns_create_multi
                if m:
                    return multi_create(m)

            name = dotted(name)
            # we allow (and filter) empty start or end comma, simplifies bash scripts a lot in loops:
            ips = [i for i in ips or FLG.dns_create_ips if i]
            ttl = ttl or FLG.dns_create_ttl
            rm = FLG.dns_create_rm
            have = c[0] or Actions.dns_list(name='*')['data']
            me = [i for i in have if name == i['name']]
            if me and me[0]['ips'] == ips:
                app.info('Already present', ips=ips, name=name)
                return 'present'
            id = [i for i in have if name.endswith(i['domain'])]
            if id:
                if rm:
                    r = [i for i in have if i['name'] == name]
                    if r:
                        Actions.dns_delete(name=name, force=True)
                id = id[0]['zoneid']
            else:
                have = c[0] or Actions.domain_list(name='*')
                id = [i for i in have['data'] if name.endswith(i['name'])]
                if len(id) != 1:
                    app.die('No matching domain', name=name, have=have['data'])
                id = id[0]['id']
            c[0] = have
            dns_modify('CREATE', ips=ips, name=name, ttl=ttl, zoneid=id)
            return Actions.dns_list(name=name)

    def dns_delete(name=None, force=None):
        name = dotted(name, False)
        return Prov().resource_delete(Prov().dns, force=force)


def dns_modify(action, ips, name, ttl, zoneid, **_):
    app.info(f'DNS {action}', **dict(locals()))
    assert action in {'CREATE', 'DELETE'}
    if not ips:
        app.die('No ips', **dict(locals()))
    rr = ''.join([TARR.format(ip=ip) for ip in ips])
    d = dict(name=name, rr=rr, ttl=ttl, base_doc=AA.base_doc, action=action)
    xml = xmlhead + '\n' + TAR.format(**d).replace('\n', '')
    path = f'hostedzone/{zoneid}/rrset'
    r = AA.send_request(path, xml, 'post')
    return r


def multi_create(m):
    zones.origget = zones.get
    if FLG.dns_create_rm:
        # speed up:
        zones.get = zones.get_cached
    Actions.dns_list(name='*')['data']
    hosts = []
    res = []
    for hip in m:
        host, ips = hip.split('::', 1)
        hosts.append(host + '.' if not host.endswith('.') else '')
        ips = ips.split(':')
        res.append(Actions.dns_create.run(name=host, ips=ips, multi=True))
    if not res == ['present', 'present']:
        zones.get = zones.origget

    def f(all, hosts=hosts):
        return [i for i in all if i['name'] in hosts]

    return Actions.dns_list(name='*', filtered=f)


class Flags(Flags):
    class aws_key:
        n = 'key or command to get it'
        d = ''

    class aws_secret:
        n = 'secret or command to get it'
        d = 'cmd: pass show AWS/pw'


Flags._pre_init(Flags, Actions)


_ = 'We will create default network, if not present yet'
# Flags.Actions.droplet_create.private_network.n += _


class AWSProv(Provider):
    name = 'AWS'
    Actions = Actions
    secrets = 'aws_key', 'aws_secret'

    def normalize_pre(d, r, cls, headers):
        return

    def rm_junk(api_response):
        return

    class domain:
        endpoint = 'hostedzone'
        normalize = []
        headers = ['name', 'id', 'comment']

    class dns:
        # fmt:off
        endpoint = 'hostedzone'
        normalize = []
        # fmt:on
        headers = ['name', 'ips', 'ttl']

        def prepare_delete(d):
            dns_modify(action='DELETE', **d)
            return fmt.flag_deleted


Prov(init=AWSProv)
main = lambda: run_app(Actions, flags=Flags)


class AA:
    """The Funny AWS API"""

    base = 'https://route53.amazonaws.com/2012-02-29'
    base_doc = 'https://route53.amazonaws.com/doc/2012-02-29'   # for posts

    def sign(s):
        _ = Api.secrets['aws_secret'].encode('utf-8')
        new_hmac = hmac.new(_, digestmod=hashlib.sha256)
        new_hmac.update(s.encode('utf-8'))
        return base64.b64encode(new_hmac.digest()).decode('utf-8')

    def get_request_headers():
        date_header = time.asctime(time.gmtime())
        sk = AA.sign(date_header)
        id = Api.secrets['aws_key']
        auth_header = (
            f'AWS3-HTTPS AWSAccessKeyId={id},Algorithm=HmacSHA256,Signature={sk}'
        )
        return {
            'X-Amzn-Authorization': auth_header,
            'x-amz-date': date_header,
            'Host': 'route53.amazonaws.com',
        }

    def send_request(path, data, method):
        app.info(f'{method} request', path=path)
        headers = AA.get_request_headers()
        ep = f'{AA.base}/{path}'
        r = getattr(requests, method)(ep, data, headers=headers)
        if app.log_level < 20:
            app.debug('repsonse', xml=r.text)
        if not r.status_code < 300:
            app.die('API Error', txt=r.text)
        return r.text


def xval(s, tag, d=''):
    # sry - but when I was young, allowing this was a main selling point of XML:
    t = f'<{tag}>'
    return d if not t in s else s.split(t, 1)[1].split(f'</{tag}>', 1)[0]


class zones:
    @cache(10)
    def get_cached(max_items=1000, get_records=True):
        return zones.origget(max_items, get_records)

    def get(max_items=1000, get_records=True):
        r = AA.send_request('hostedzone', {'maxitems': 1000}, 'get')
        assert 'ListHostedZonesResponse' in r
        All = []
        for hz in r.split('<HostedZone>')[1:]:
            id = xval(hz, 'Id')[1:].replace('hostedzone/', '')
            dom_name = xval(hz, 'Name')
            if not get_records:
                comment = xval(hz, 'Comment')
                All.append({'id': id, 'name': dom_name, 'comment': comment})
                continue
            d = {'identifier': None, 'maxitems': 1000, 'name': None, 'type': None}
            r = AA.send_request(f'hostedzone/{id}/rrset', d, 'get')
            assert 'ListResourceRecordSetsResponse' in r

            def d(s, id=id):
                r = {
                    'domain': dom_name,
                    'name': xval(s, 'Name'),
                    'type': xval(s, 'Type'),
                    'ttl': int(xval(s, 'TTL', 0)),
                    'zoneid': id,
                }
                if not r['type'] == 'A':
                    return

                r['ips'] = [xval(k, 'Value') for k in s.split('<ResourceRecord>')[1:]]
                return r

            all = [d(s) for s in r.split('<ResourceRecordSet>')[1:]]
            all = sorted([k for k in all if k], key=lambda d: d['name'])
            All.extend(all)
        return All


def get_domains():
    return zones.get(max_items=100, get_records=False)


xmlhead = "<?xml version='1.0' encoding='UTF-8'?>"
# template a record:
TAR = """
<ChangeResourceRecordSetsRequest xmlns="{base_doc}/"><ChangeBatch>
<Changes><Change><Action>{action}
</Action><ResourceRecordSet><Name>{name}
</Name><Type>A
</Type><TTL>{ttl}
</TTL><ResourceRecords>{rr}</ResourceRecords>
</ResourceRecordSet>
</Change>
</Changes>
</ChangeBatch>
</ChangeResourceRecordSetsRequest>"""
TARR = '<ResourceRecord><Value>{ip}</Value></ResourceRecord>'


TCertMgr = """
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
  namespace: cert-manager
spec:
  acme:
    email: "{email}"
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-prod-issuer-account-key
    solvers:
      - selector:
          dnsZones:
            - "{zone}"
        dns01:
          route53:
            region: eu-west-3
            accessKeyID: "{id}"
            secretAccessKeySecretRef:
              name: prod-route53-credentials-secret
              key: secret-access-key
"""

TEXTDNS = """
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: external-dns
  namespace: external-dns
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: external-dns
rules:
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "watch", "list"]
  - apiGroups: ["gateway.networking.k8s.io"]
    resources: ["gateways", "httproutes", "tlsroutes", "tcproutes", "udproutes"]
    verbs: ["get", "watch", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: external-dns
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: external-dns
subjects:
  - kind: ServiceAccount
    name: external-dns
    namespace: external-dns

"""

T_EXTDNS_DEPL = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: external-dns
  namespace: external-dns
spec:
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: external-dns
  template:
    metadata:
      labels:
        app: external-dns
    spec:
      serviceAccountName: external-dns
      containers:
        - name: external-dns
          image: k8s.gcr.io/external-dns/external-dns:v{version}
          args:
            - --log-level=debug
            - --source=gateway-httproute
            - --source=gateway-tlsroute
            - --source=gateway-tcproute
            - --source=gateway-udproute
            - --interval=1m
            - --policy=upsert-only
            - --registry=txt
            - --txt-owner-id={user}
            - --domain-filter={zone}
            - --provider=aws
            - --aws-zone-type=public
          resources:
            limits:
              memory: 1024M
            requests:
              cpu: 100m
              memory: 64Mi
          env:
            - name: AWS_SHARED_CREDENTIALS_FILE
              value: /.aws/credentials
          volumeMounts:
            - name: aws-credentials
              mountPath: /.aws
              readOnly: true
      volumes:
        - name: aws-credentials
          secret:
            secretName: external-dns-aws
"""


TINI = """
[default]
aws_access_key_id = {key}
aws_secret_access_key = {secret}
"""

if __name__ == '__main__':
    main()
