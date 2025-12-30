# VPS Manager Documentation

## Template Variables

The VPS Manager uses a template system for NGINX configurations. You can use the following variables in your configuration templates:

### Available Variables

- `$DOMAIN` - The domain name (e.g., `example.com`)
- `$PORT` - The backend port number (e.g., `3000`)
- `$BACKEND_IP` - The backend IP address (automatically detected VPS IP for Docker compatibility)
- `$SSL_CERT_PATH` - Path to SSL certificate file
- `$SSL_KEY_PATH` - Path to SSL private key file
- `$MANAGER_DIR` - Path to the manager directory (`~/manager`)
- `$NGINX_SITES_DIR` - Path to NGINX sites-available directory
- `$NGINX_ENABLED_DIR` - Path to NGINX sites-enabled directory

### Default Template

The default template (`~/manager/templates/default.conf`) includes:
- HTTP to HTTPS redirection
- SSL configuration with modern security settings
- Proxy pass to backend application
- Static file optimization
- Gzip compression
- Security headers
- Access and error logging

## Custom Configurations

### Creating Custom Templates

1. Create a new `.conf` file in `~/manager/custom-configs/`
2. Use the template variables listed above
3. Follow NGINX configuration syntax
4. Test your configuration before applying

### Example Custom Configuration

```nginx
# Custom configuration for API server
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    # SSL Configuration
    ssl_certificate $SSL_CERT_PATH;
    ssl_certificate_key $SSL_KEY_PATH;
    
    # Custom API-specific settings
    client_max_body_size 50M;
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
    
    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:$PORT/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:$PORT/health;
        access_log off;
    }
    
    # Static files (if any)
    location /static/ {
        alias /var/www/$DOMAIN/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Configuration Guidelines

1. **Always include SSL configuration** if you plan to use HTTPS
2. **Use template variables** instead of hardcoded values
3. **Include proper proxy headers** for backend applications
4. **Set appropriate timeouts** based on your application needs
5. **Configure logging** for debugging and monitoring
6. **Test configurations** before applying to production

## Directory Structure

```
vps-manager/
├── src/
│   └── vps_manager/
│       ├── __init__.py
│       ├── main.py        # Entry point
│       ├── core.py        # Core logic
│       ├── ui.py          # User interface
│       └── utils.py       # Utilities
├── tests/                 # Unit tests
└── setup.py               # Package configuration

# Runtime data (created in ~/manager/ during use):
~/manager/
├── domains.json            # Domain configurations
├── custom-configs/
│   ├── api-server.conf     # Custom template example
│   └── static-site.conf    # Another custom template
├── backups/
│   ├── backup_20240101_120000.tar.gz
│   └── backup_20240102_120000.tar.gz
└── logs/
    └── manager.log         # Application logs
```

## SSL Certificate Management

### Automatic Certificate Generation

The manager automatically handles SSL certificates using Certbot:

1. **Domain validation** - Ensures domain points to your server
2. **Certificate generation** - Uses Let's Encrypt via Certbot
3. **Auto-renewal** - Certificates are automatically renewed
4. **NGINX integration** - Certificates are automatically configured

### Manual Certificate Management

If you need to manage certificates manually:

```bash
# Generate certificate manually
sudo certbot certonly --nginx -d your-domain.com

# Renew certificates
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run
```

## Backup and Restore

### Automatic Backups

The manager creates backups that include:
- Domain configurations (`domains.json`)
- NGINX site configurations
- SSL certificates
- Custom templates
- Application logs

### Manual Backup

```bash
# Create manual backup
cd ~/manager
tar -czf backups/manual_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    domains.json templates/ custom-configs/ \
    /etc/nginx/sites-available/ \
    /etc/letsencrypt/
```

### Restore Process

1. Select backup from the manager interface
2. Confirm restoration (this overwrites current configs)
3. NGINX is automatically reloaded
4. Verify all domains are working correctly

## Troubleshooting

### Common Issues

1. **Domain not accessible**
   - Check DNS settings
   - Verify NGINX is running: `sudo systemctl status nginx`
   - Test configuration: `sudo nginx -t`

2. **SSL certificate errors**
   - Ensure domain points to your server
   - Check Certbot logs: `sudo tail -f /var/log/letsencrypt/letsencrypt.log`
   - Verify port 80 and 443 are open

3. **Backend connection errors**
   - Verify backend application is running
   - Check port configuration
   - Review NGINX error logs

### Log Files

- **NGINX Error Log**: `/var/log/nginx/error.log`
- **NGINX Access Log**: `/var/log/nginx/access.log`
- **Certbot Log**: `/var/log/letsencrypt/letsencrypt.log`
- **Manager Log**: `~/manager/logs/manager.log`
- **System Log**: `journalctl -u nginx`

### Useful Commands

```bash
# Test NGINX configuration
sudo nginx -t

# Reload NGINX
sudo systemctl reload nginx

# Restart NGINX
sudo systemctl restart nginx

# Check NGINX status
sudo systemctl status nginx

# View real-time error logs
sudo tail -f /var/log/nginx/error.log

# List SSL certificates
sudo certbot certificates

# Renew SSL certificates
sudo certbot renew
```

## Security Considerations

1. **Keep system updated**: Regular security updates
2. **Firewall configuration**: Only open necessary ports
3. **SSL/TLS settings**: Use modern, secure configurations
4. **Access logs**: Monitor for suspicious activity
5. **Backup encryption**: Consider encrypting sensitive backups
6. **User permissions**: Run with appropriate privileges

## Performance Optimization

1. **Gzip compression**: Enabled by default in templates
2. **Static file caching**: Configure appropriate cache headers
3. **Connection limits**: Set reasonable limits for your server
4. **Worker processes**: Optimize NGINX worker configuration
5. **Buffer sizes**: Adjust based on your application needs

## Support and Updates

For issues, feature requests, or updates:
1. Check the troubleshooting section
2. Review log files for error details
3. Test configurations in a safe environment
4. Keep backups before making changes

---

*This documentation covers the core functionality of the VPS Manager. For advanced configurations or specific use cases, refer to the NGINX and Certbot official documentation.*