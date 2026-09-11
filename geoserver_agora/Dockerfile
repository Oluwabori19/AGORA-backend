ARG BASE_IMAGE_VERSION
FROM dcs-base-geoserver:2.27.6

ARG GEOSERVER_CORS_ENABLED=True
ENV GEOSERVER_CORS_ENABLED=$GEOSERVER_CORS_ENABLED

## GeoServer plugins
# Make sure GeoServer container is prepared for each plugin!
# Use further RUN statements to install neccessary dependencies.
# Refer to plugin documentation what is required to use a plugin.
COPY ./plugins /usr/local/tomcat/webapps/geoserver/WEB-INF/lib
CMD ["/usr/local/tomcat/tmp/entrypoint.sh"]
