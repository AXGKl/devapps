#!/usr/bin/env python
"""
# Hetzner Infrastructure Tool

https://www.hetzner.com/cloud/#pricing

## Purpose
Low level Operations on the DO Cloud, using their REST API
E.g. when terraform destroy fails, you can delete droplets using this.

## Caution

Most features are tested against a Fedora host filesystem (the default image)

## Requirements
- API Token

## Examples:

### Listing
- ops ihc
- ops ihc --since 10h
- ops ihc -m "*foo*"

### Creation
- ops ihc dc -n mydroplet                             # create a minimal droplet
- ops ihc dc -n mydroplet -sac -f k3s -s m-2vcpu-16gb # create a droplet with this size, name foo, with k3s feature

### Deletion
- ops ihc dd --since 1h # delete all created within the last hour (-f skips confirm)

## Misc

See Actions at -h
"""


from devapp.app import run_app, FLG, app
from devapp.tools.infra import Actions, Flags, Provider, Api, Prov, fmt, rm
from operator import setitem

# Droplet list results are cached in tmp/droplets.json. We will read from here if recent.'
# droplet_list_cache_max_age = int(os.environ.get('droplet_list_cache_max_age', 3))


class Actions(Actions):
    def prices():
        return Api.get('pricing')

    def placement_group_list(name=None):
        return Prov().list_simple(
            name,
            Prov().placement_group,
            headers=['id', 'name', fmt.key_tags, 'since', fmt.key_droplets],
        )

    def placement_group_create(name=None, type='spread'):
        name = FLG.name if name is None else name
        d = dict(locals())
        Api.req(Prov().placement_group.endpoint, 'post', data=d)
        return Actions.placement_group_list(name=name)

    placement_group_delete = rm('placement_group')


class Flags(Flags):
    class hcloud_api_token:
        d = 'cmd:pass show HCloud/token'


Flags._pre_init(Flags, Actions)


Flags.region.d = 'hel1'
Flags.image.d = 'fedora-36'
_ = 'We will create default network, if not present yet'
# Flags.Actions.droplet_create.private_network.n += _


def monthly(server_type, region, which='monthly'):
    s = server_type
    p = [l for l in s['prices'] if l['location'] == region]
    if not p:
        app.info(
            'Not available in region',
            name=s['name'],
            region=FLG.region,
        )
        return -1
    return round(float(p[0][f'price_{which}']['gross']), 2)


def fmt_region(key, d, into):
    l = d['datacenter']['location'] if 'datacenter' in d else d['location']
    into['region'] = l['name']


fmt_tags = lambda key, d, into: setitem(
    into, 'tags', [f'{k}:{v}' for k, v in d['labels'].items()]
)
fmt_ip_ranges = lambda key, d, into: setitem(
    into, 'iprange', [i['ip_range'] for i in d[key]]
)


def fmt_ips(key, d, into):
    r = into
    try:
        r['ip_priv'] = d['private_net'][0]['ip']
    except:
        pass
    for k, t in (['ip', 'public_net'],):
        try:
            r[k] = d[t]['ipv4']['ip']
        except:
            pass


def fmt_price(key, d, into):
    if key == 'prices':
        into[fmt.key_price_monthly] = monthly(d, FLG.region)   # size list
    else:
        st = d['server_type']
        into[fmt.key_typ] = fmt.typ(st['cores'], int(st['memory']), st['disk'])
        reg = d['datacenter']['location']['name']   # droplet
        into[fmt.key_curncy] = monthly(st, reg)
        fmt.price_total(key, d, into, monthly(st, reg, 'hourly'))


def fmt_target_to_servers(_, d, into):
    t = d['targets']
    if not t:
        d['servers'] = []
        return
    # we've seen 2 formats of targets, once nested one direct, dependent no label sel presence
    if 'server' in t[0]:
        return [s['server']['id'] for s in t]
    d['servers'] = [i['server']['id'] for k in range(len(t)) for i in t[k]['targets']]


class HProv(Provider):
    name = 'Hetzner'
    secrets = 'hcloud_api_token'
    base_url = 'https://api.hetzner.cloud/v1'
    vol_price_gig_month = 0.0476   # https://www.hetzner.com/cloud/#pricing
    pgroup = None
    Actions = Actions

    # fmt:off
    alias_sizes = [
        ['XXS'      , 'cpx11'         ],
        ['XS'       , 'cx31'          ],
        ['S'        , 'ccx12'         ],
        ['M'        , 'ccx32'         ],
        ['L'        , 'ccx52'         ],
        ['XL'       , 'ccx62'         ],
    ]
    # fmt:on

    def normalize_pre(d, r, cls, headers):
        if 'created' in d:
            fmt.to_since('created', d, r)
        if 'datacenter' in d or 'location' in d:
            fmt_region('', d, r)
        if 'labels' in d:
            fmt_tags('labels', d, r)
        if 'targets' in d:   # loadbalancer
            fmt_target_to_servers('', d, r)
        if 'servers' in d:
            fmt.droplet_id_to_name('servers', d, r)
        if 'server' in d:
            fmt.droplet_id_to_name('server', d, r)
        if 'public_net' in d:
            fmt_ips('', d, r)

    def rm_junk(api_response):
        try:
            [i['datacenter'].pop('server_types') for i in api_response]
        except:
            pass

    class droplet:
        # fmt:off
        endpoint = 'servers'

        normalize = [
            ['volumes'     , fmt.volumes  ] ,
            ['id'          , fmt_ips      ] ,
            ['server_type' , fmt_price    ] ,
        ]
        # fmt:on

        def prepare_create(env):
            if not FLG.range:
                return app.info('Skipping placement group for single droplet')
            A, cn = Prov().Actions, env['cluster_name']

            def h(k):
                i = [i for i in k['data'] if i['name'] == cn]
                return i[0] if i else None

            HProv.pgroup = _ = h(A.placement_group_list())
            if _:
                return
            HProv.pgroup = h(A.placement_group_create(cn))

        def create_data(d):
            r = dict(d)
            if HProv.pgroup:
                r['placement_group'] = HProv.pgroup['id']
            pn = r.pop('private_network')
            r['networks'] = [Prov().NETWORKS[pn]['id']]
            r['automount'] = False
            r['location'] = r.pop('region')
            t = r.pop('tags')
            if t:
                r['labels'] = {'feats': ','.join([i.replace(':', '_') for i in t])}
            r['server_type'] = r.pop('size')
            return r

    class image:
        # fmt:off
        endpoint = 'images'
        normalize = [
            ['disk_size'    , fmt.key_disk_size ] ,
            ['rapid_deploy' , 'rapid'           ] ,
        ]
        # fmt:on

    class load_balancer:
        endpoint = 'load_balancers'

    class network:
        endpoint = 'networks'
        default = lambda: 'default'
        normalize = [['subnets', fmt_ip_ranges]]

        def create_data(d):
            i = d['ip_range']
            if not i.startswith('10.'):
                app.die('ip range must start with 10.', have=i)
            d['ip_range'] = '10.0.0.0/8'
            d['subnets'] = [
                {
                    'network_zone': 'eu-central',  # only option
                    'ip_range': i,
                    'type': 'cloud',
                }
            ]
            return d

    class placement_group:
        endpoint = 'placement_groups'

    class ssh_keys:
        endpoint = 'ssh_keys'
        normalize = [['public_key', fmt.ssh_pub_key]]

    class sizes:
        # fmt:off
        endpoint = 'server_types?per_page=100'
        normalize = [
            ['name'        , fmt.size_name_and_alias ] ,
            ['prices'      , fmt_price               ] ,
            ['cores'       , 'CPU'                   ] ,
            ['memory'      , fmt.to_ram              ] ,
            ['disk'        , fmt.key_disk_size       ] ,
            ['description' , 'Descr'                 ] ,
        ]
        # fmt:on

    class volume:
        # fmt:off
        endpoint = 'volumes'
        normalize = [
            ['size'     , fmt.key_disk_size      ] ,
            ['id'       , fmt.vol_price          ] ,
        ]
        # fmt:on

        def create_data(d):
            r = dict(d)
            s, rg = d.pop('_attach_to', ''), d.pop('region')
            if s:
                r['server'] = s['server']['id']
                # r['automount'] = True
            else:
                r['location'] = rg
            t = r.pop('tags')
            return r

        def prepare_delete(d):
            s = d.get('server')
            if not s:
                return
            id = d['id']
            app.warn('detaching', **d)
            Api.req(f'volumes/{id}/actions/detach', 'post', data={})


Prov(init=HProv)
Flags.size.n = 'aliases ' + HProv.size_aliases()
main = lambda: run_app(Actions, flags=Flags)

if __name__ == '__main__':
    main()
