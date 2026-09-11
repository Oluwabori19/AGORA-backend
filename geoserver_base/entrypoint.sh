#!/bin/bash
set -e

source /root/.bashrc

# configure CORS (inspired by https://github.com/oscarfonts/docker-geoserver)
# if enabled, this will add the filter definitions
# to the end of the web.xml
# (this will only happen if our filter has not yet been added before)
echo "Starting entrypoint script to configure CORS..."
if [ "${GEOSERVER_CORS_ENABLED}" = "true" ] || [ "${GEOSERVER_CORS_ENABLED}" = "True" ]; then
  if ! grep -q DockerGeoServerCorsFilter "$CATALINA_HOME/webapps/geoserver/WEB-INF/web.xml"; then
    echo "Enable CORS for $CATALINA_HOME/webapps/geoserver/WEB-INF/web.xml"
    sed -i "\:</web-app>:i\\
    <filter>\n\
      <filter-name>DockerGeoServerCorsFilter</filter-name>\n\
      <filter-class>org.apache.catalina.filters.CorsFilter</filter-class>\n\
      <init-param>\n\
          <param-name>cors.allowed.origins</param-name>\n\
          <param-value>*</param-value>\n\
      </init-param>\n\
      <init-param>\n\
          <param-name>cors.allowed.methods</param-name>\n\
          <param-value>GET,POST,HEAD,OPTIONS,PUT</param-value>\n\
      </init-param>\n\
      <init-param>\n\
        <param-name>cors.allowed.headers</param-name>\n\
        <param-value>Content-Type,X-Requested-With,accept,Access-Control-Request-Method,Access-Control-Request-Headers,If-Modified-Since,Range,Origin,Authorization</param-value>\n\
      </init-param>\n\
      <init-param>\n\
        <param-name>cors.exposed.headers</param-name>\n\
        <param-value>Access-Control-Allow-Origin,Access-Control-Allow-Credentials</param-value>\n\
      </init-param>\n\
      <init-param>\n\
        <param-name>cors.support.credentials</param-name>\n\
        <param-value>False</param-value>\n\
      </init-param>\n\
      <init-param>\n\
        <param-name>cors.preflight.maxage</param-name>\n\
        <param-value>10</param-value>\n\
      </init-param>\n\
    </filter>\n\
    <filter-mapping>\n\
      <filter-name>DockerGeoServerCorsFilter</filter-name>\n\
      <url-pattern>/*</url-pattern>\n\
    </filter-mapping>" "$CATALINA_HOME/webapps/geoserver/WEB-INF/web.xml";
  fi
fi
echo "CORS configuration completed."
if [ "${FORCE_REINIT}" = "true" ] || [ "${FORCE_REINIT}" = "True" ] || [ ! -e "${GEOSERVER_DATA_DIR}/geoserver_init.lock" ]; then
    # Run async configuration, it needs Geoserver to be up and running
    nohup sh -c "invoke configure-geoserver" &
fi

# start tomcat
exec env JAVA_OPTS="${JAVA_OPTS}" catalina.sh run