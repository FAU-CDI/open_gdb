# RDF4J server and workbench with the OpenGDB change log Sail (opengdb:ChangeLogSail).
# Without a repository that uses that Sail type, the image behaves like the stock image.
ARG RDF4J_VERSION=6.1.0

FROM maven:3.9-eclipse-temurin-25 AS build
WORKDIR /src
COPY changelog-sail/pom.xml changelog-sail/
RUN mvn -f changelog-sail/pom.xml -B -q dependency:go-offline
COPY changelog-sail changelog-sail
RUN mvn -f changelog-sail/pom.xml -B package

FROM eclipse/rdf4j-workbench:${RDF4J_VERSION}-tomcat
USER root
# Only the server instantiates Sails; the workbench doesn't need the jar.
COPY --from=build /src/changelog-sail/target/opengdb-changelog-sail.jar /tmp/inject/WEB-INF/lib/
RUN cd /tmp/inject \
 && jar uf /usr/local/tomcat/webapps/rdf4j-server.war WEB-INF/lib/opengdb-changelog-sail.jar \
 && rm -rf /tmp/inject \
 && chown tomcat /usr/local/tomcat/webapps/rdf4j-server.war
USER tomcat
