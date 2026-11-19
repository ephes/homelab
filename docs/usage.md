# Usage

## Dashboard

Access your services at http://localhost:8000 (or your production URL).

## Connection diagnostics

Open `/connection-info/` to see the client address and proxy information for
the current request. The Tailscale badge covers IPv4 and IPv6 tailnet addresses,
including IPv4-mapped IPv6 addresses for the IPv4 range. The response uses `Cache-Control: private, no-store`.

## Managing Services

### Via Admin Panel

1. Go to `/admin/`
2. Click Services → Add Service
3. Fill in:
   - **Name**: Service name
   - **URL**: Full URL with https://
   - **Icon**: Font Awesome class
   - **Order**: Display position

### Service Organization

- Lower order numbers appear first
- Use increments of 10 for easy reordering
- Deactivate services to hide temporarily

### Common Icons

| Service | Icon |
|---------|------|
| Cloud Storage | `fas fa-cloud` |
| Media Server | `fas fa-film` |
| Home Assistant | `fas fa-home` |
| Docker | `fab fa-docker` |
| Monitoring | `fas fa-chart-line` |

Find more at [fontawesome.com](https://fontawesome.com/icons)

## Import/Export

```bash
# Export services
just manage dumpdata core.service > services.json

# Import services  
just manage loaddata services.json
```

## Tips

- Always use full URLs with protocol
- Group related services with similar order numbers
- Use descriptive names and icons
- Test service URLs before adding