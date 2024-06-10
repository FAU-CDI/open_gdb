## Repository:
From a get request on the `/rest/repositories/{repositoryID} endpoint:

With `{Content-Type: application/json}`
```json
{
  "id": "test",
  "title": "something",
  "type": "graphdb",
  "sesameType": "graphdb:SailRepository",
  "location": "",
  "params": {
    "queryTimeout": {
      "name": "queryTimeout",
      "label": "Query timeout (seconds)",
      "value": "0"
    },
    "cacheSelectNodes": {
      "name": "cacheSelectNodes",
      "label": "Cache select nodes",
      "value": "true"
    },
    "rdfsSubClassReasoning": {
      "name": "rdfsSubClassReasoning",
      "label": "RDFS subClass reasoning",
      "value": "true"
    },
    "validationEnabled": {
      "name": "validationEnabled",
      "label": "Enable the SHACL validation",
      "value": "true"
    },
    "ftsStringLiteralsIndex": {
      "name": "ftsStringLiteralsIndex",
      "label": "FTS index for xsd:string literals",
      "value": "default"
    },
    "shapesGraph": {
      "name": "shapesGraph",
      "label": "Named graphs for SHACL shapes",
      "value": "http://rdf4j.org/schema/rdf4j#SHACLShapeGraph"
    },
    "parallelValidation": {
      "name": "parallelValidation",
      "label": "Run parallel validation",
      "value": "true"
    },
    "checkForInconsistencies": {
      "name": "checkForInconsistencies",
      "label": "Enable consistency checks",
      "value": "false"
    },
    "performanceLogging": {
      "name": "performanceLogging",
      "label": "Log the execution time per shape",
      "value": "false"
    },
    "disableSameAs": {
      "name": "disableSameAs",
      "label": "Disable owl:sameAs",
      "value": "true"
    },
    "ftsIrisIndex": {
      "name": "ftsIrisIndex",
      "label": "FTS index for full-text indexing of IRIs",
      "value": "none"
    },
    "entityIndexSize": {
      "name": "entityIndexSize",
      "label": "Entity index size",
      "value": "10000000"
    },
    "dashDataShapes": {
      "name": "dashDataShapes",
      "label": "DASH data shapes extensions",
      "value": "true"
    },
    "queryLimitResults": {
      "name": "queryLimitResults",
      "label": "Limit query results",
      "value": "0"
    },
    "throwQueryEvaluationExceptionOnTimeout": {
      "name": "throwQueryEvaluationExceptionOnTimeout",
      "label": "Throw exception on query timeout",
      "value": "false"
    },
    "member": {
      "name": "member",
      "label": "FedX repo members",
      "value": []
    },
    "storageFolder": {
      "name": "storageFolder",
      "label": "Storage folder",
      "value": "storage"
    },
    "validationResultsLimitPerConstraint": {
      "name": "validationResultsLimitPerConstraint",
      "label": "Validation results limit per constraint",
      "value": "1000"
    },
    "enablePredicateList": {
      "name": "enablePredicateList",
      "label": "Enable predicate list index",
      "value": "true"
    },
    "transactionalValidationLimit": {
      "name": "transactionalValidationLimit",
      "label": "Transactional validation limit",
      "value": "500000"
    },
    "ftsIndexes": {
      "name": "ftsIndexes",
      "label": "FTS indexes to build (comma delimited)",
      "value": "default, iri"
    },
    "logValidationPlans": {
      "name": "logValidationPlans",
      "label": "Log the executed validation plans",
      "value": "false"
    },
    "imports": {
      "name": "imports",
      "label": "Imported RDF files(';' delimited)",
      "value": ""
    },
    "isShacl": {
      "name": "isShacl",
      "label": "Enable SHACL validation",
      "value": "false"
    },
    "inMemoryLiteralProperties": {
      "name": "inMemoryLiteralProperties",
      "label": "Cache literal language tags",
      "value": "true"
    },
    "ruleset": {
      "name": "ruleset",
      "label": "Ruleset",
      "value": "rdfsplus-optimized"
    },
    "readOnly": {
      "name": "readOnly",
      "label": "Read-only",
      "value": "false"
    },
    "enableLiteralIndex": {
      "name": "enableLiteralIndex",
      "label": "Enable literal index",
      "value": "true"
    },
    "enableFtsIndex": {
      "name": "enableFtsIndex",
      "label": "Enable full-text search (FTS) index",
      "value": "false"
    },
    "defaultNS": {
      "name": "defaultNS",
      "label": "Default namespaces for imports(';' delimited)",
      "value": ""
    },
    "enableContextIndex": {
      "name": "enableContextIndex",
      "label": "Enable context index",
      "value": "false"
    },
    "baseURL": {
      "name": "baseURL",
      "label": "Base URL",
      "value": "http://example.org/owlim#"
    },
    "logValidationViolations": {
      "name": "logValidationViolations",
      "label": "Log validation violations",
      "value": "false"
    },
    "globalLogValidationExecution": {
      "name": "globalLogValidationExecution",
      "label": "Log every execution step of the SHACL validation",
      "value": "false"
    },
    "entityIdSize": {
      "name": "entityIdSize",
      "label": "Entity ID size",
      "value": "32"
    },
    "repositoryType": {
      "name": "repositoryType",
      "label": "Repository type",
      "value": "file-repository"
    },
    "eclipseRdf4jShaclExtensions": {
      "name": "eclipseRdf4jShaclExtensions",
      "label": "RDF4J SHACL extensions",
      "value": "true"
    },
    "validationResultsLimitTotal": {
      "name": "validationResultsLimitTotal",
      "label": "Validation results limit total",
      "value": "1000000"
    }
  }
}
```

With `{Content-Type: text/turtle}`:
```ttl
#
# RDF4J configuration template for a GraphDB repository
#
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
@prefix rep: <http://www.openrdf.org/config/repository#>.
@prefix sr: <http://www.openrdf.org/config/repository/sail#>.
@prefix sail: <http://www.openrdf.org/config/sail#>.
@prefix graphdb: <http://www.ontotext.com/config/graphdb#>.

[] a rep:Repository ;
    rep:repositoryID "test" ;
    rdfs:label "" ;
    rep:repositoryImpl [
        rep:repositoryType "graphdb:SailRepository" ;
        sr:sailImpl [
            sail:sailType "graphdb:Sail" ;

            graphdb:read-only "false" ;

            # Inference and Validation
            graphdb:ruleset "rdfsplus-optimized" ;
            graphdb:disable-sameAs "true" ;
            graphdb:check-for-inconsistencies "false" ;

            # Indexing
            graphdb:entity-id-size "32" ;
            graphdb:enable-context-index "false" ;
            graphdb:enablePredicateList "true" ;
            graphdb:enable-fts-index "false" ;
            graphdb:fts-indexes ("default" "iri") ;
            graphdb:fts-string-literals-index "default" ;
            graphdb:fts-iris-index "none" ;

            # Queries and Updates
            graphdb:query-timeout "0" ;
            graphdb:throw-QueryEvaluationException-on-timeout "false" ;
            graphdb:query-limit-results "0" ;

            # Settable in the file but otherwise hidden in the UI and in the RDF4J console
            graphdb:base-URL "http://example.org/owlim#" ;
            graphdb:defaultNS "" ;
            graphdb:imports "" ;
            graphdb:repository-type "file-repository" ;
            graphdb:storage-folder "storage" ;
            graphdb:entity-index-size "10000000" ;
            graphdb:in-memory-literal-properties "true" ;
            graphdb:enable-literal-index "true" ;
        ]
    ].
```

