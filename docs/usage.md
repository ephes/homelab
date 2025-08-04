# Usage

## Dashboard

Access your services at http://localhost:8000 (or your production URL).

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