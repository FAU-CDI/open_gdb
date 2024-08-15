# Generated by Django 5.0.4 on 2024-05-27 16:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rdf4j", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="repository",
            name="turtle_template",
            field=models.TextField(
                default='\n        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.\n        @prefix config: <tag:rdf4j.org,2023:config/>.\n\n        [] a config:Repository ;\n        config:rep.id "${slug}" ;\n        rdfs:label "${description}" ;\n        config:rep.impl [\n            config:rep.type "openrdf:SailRepository" ;\n            config:sail.impl [\n                config:sail.type "openrdf:NativeStore" ;\n                config:native.tripleIndexes "spoc,opsc,cspo"\n            ]\n        ].\n        ',
                help_text="Template for the repo ceation, passed though to RDF4J.\n    Available variables:\n    - ${slug}: The slug of the repo\n    - ${description}: The description of the repo\n    ",
                null=True,
            ),
        ),
        migrations.DeleteModel(
            name="SailConfiguration",
        ),
    ]
