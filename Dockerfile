FROM ubuntu:24.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    certbot \
    python3-certbot-nginx \
    curl \
    sudo \
    nano \
    net-tools \
    iputils-ping \
    procps \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Create a fake systemctl to mock systemd interactions
RUN echo '#!/bin/bash\n\
action=$1\n\
service=$2\n\
\n\
if [ "$service" == "nginx" ]; then\n\
    if [ "$action" == "reload" ]; then\n\
        nginx -s reload\n\
    elif [ "$action" == "restart" ]; then\n\
        nginx -s stop 2>/dev/null\n\
        sleep 1\n\
        nginx\n\
    elif [ "$action" == "is-active" ]; then\n\
        if pgrep nginx > /dev/null; then\n\
            echo "active"\n\
        else\n\
            echo "inactive"\n\
            exit 1\n\
        fi\n\
    fi\n\
else\n\
    echo "Mock systemctl: $action $service ignored"\n\
fi' > /usr/local/bin/systemctl && chmod +x /usr/local/bin/systemctl

# Create a mock certbot for testing without real domains
RUN mv /usr/bin/certbot /usr/bin/certbot-real 2>/dev/null || true
RUN echo '#!/bin/bash\n\
if [ "$MOCK_CERTBOT" == "true" ]; then\n\
    echo "Mocking certbot..."\n\
    # Extract domain from arguments (assuming -d domain)\n\
    domain=""\n\
    args=("$@")\n\
    for ((i=0; i<${#args[@]}; i++)); do\n\
        if [[ "${args[i]}" == "-d" ]]; then\n\
            domain="${args[i+1]}"\n\
            break\n\
        fi\n\
    done\n\
    \n\
    if [ -n "$domain" ]; then\n\
        mkdir -p "/etc/letsencrypt/live/$domain"\n\
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\\n\
            -keyout "/etc/letsencrypt/live/$domain/privkey.pem" \\\n\
            -out "/etc/letsencrypt/live/$domain/fullchain.pem" \\\n\
            -subj "/CN=$domain" 2>/dev/null\n\
        echo "Mock certificate created for $domain"\n\
        exit 0\n\
    else\n\
        echo "No domain specified for mock certbot"\n\
        exit 1\n\
    fi\n\
else\n\
    if [ -f /usr/bin/certbot-real ]; then\n\
        /usr/bin/certbot-real "$@"\n\
    else\n\
        echo "Real certbot not found"\n\
        exit 1\n\
    fi\n\
fi' > /usr/bin/certbot && chmod +x /usr/bin/certbot

# Set up working directory
WORKDIR /root/manager

# Copy the package structure
COPY setup.py requirements.txt ./
COPY src/ ./src/

# Install the VPS Manager package
RUN pip3 install -e . --break-system-packages

# Copy the rest of the application files
COPY . .

# Create templates directory and copy default template
RUN mkdir -p /root/manager/templates
RUN cp /root/manager/default.conf /root/manager/templates/default.conf

# Make the entrypoint script executable
RUN chmod +x entrypoint.sh

# Expose ports
EXPOSE 80 443

# Use the entrypoint script with bash
ENTRYPOINT ["/bin/bash", "/root/manager/entrypoint.sh"]
