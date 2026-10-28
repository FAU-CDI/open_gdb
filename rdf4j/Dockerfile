# RDF4J server and workbench with the OpenGDB change log Sail (opengdb:ChangeLogSail).
# Without a repository that uses that Sail type, the image behaves like the stock image.
ARG RDF4J_VERSION=6.1.0

# The jar and the war are platform independent, so every RUN happens on the build platform:
# an arm64 image builds without emulating Java.
FROM --platform=$BUILDPLATFORM eclipse/rdf4j-workbench:${RDF4J_VERSION}-tomcat AS upstream

FROM --platform=$BUILDPLATFORM maven:3.9-eclipse-temurin-25 AS build
WORKDIR /src
COPY changelog-sail/pom.xml changelog-sail/
RUN mvn -f changelog-sail/pom.xml -B -q dependency:go-offline
COPY changelog-sail changelog-sail
RUN mvn -f changelog-sail/pom.xml -B package
# Only the server instantiates Sails; the workbench doesn't need the jar.
COPY --from=upstream /usr/local/tomcat/webapps/rdf4j-server.war /src/war/
RUN mkdir -p /src/inject/WEB-INF/lib \
 && cp changelog-sail/target/opengdb-changelog-sail.jar /src/inject/WEB-INF/lib/ \
 && cd /src/inject \
 && jar uf /src/war/rdf4j-server.war WEB-INF/lib/opengdb-changelog-sail.jar

FROM eclipse/rdf4j-workbench:${RDF4J_VERSION}-tomcat
COPY --from=build --chown=tomcat /src/war/rdf4j-server.war /usr/local/tomcat/webapps/rdf4j-server.war
