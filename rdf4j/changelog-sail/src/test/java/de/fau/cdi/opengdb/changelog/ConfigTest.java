package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.Fixture.ex;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.StringReader;
import java.nio.file.Path;

import org.eclipse.rdf4j.model.Model;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.impl.LinkedHashModel;
import org.eclipse.rdf4j.model.util.Models;
import org.eclipse.rdf4j.model.vocabulary.CONFIG;
import org.eclipse.rdf4j.repository.Repository;
import org.eclipse.rdf4j.repository.RepositoryConnection;
import org.eclipse.rdf4j.repository.config.RepositoryConfig;
import org.eclipse.rdf4j.repository.manager.LocalRepositoryManager;
import org.eclipse.rdf4j.repository.sail.SailRepository;
import org.eclipse.rdf4j.rio.RDFFormat;
import org.eclipse.rdf4j.rio.Rio;
import org.eclipse.rdf4j.sail.config.SailConfigException;
import org.eclipse.rdf4j.sail.config.SailConfigUtil;
import org.eclipse.rdf4j.sail.config.SailImplConfig;
import org.eclipse.rdf4j.sail.nativerdf.NativeStore;
import org.eclipse.rdf4j.sail.nativerdf.config.NativeStoreConfig;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import de.fau.cdi.opengdb.changelog.config.ChangeLogSailConfig;

class ConfigTest {

	/** authproxy's template for repositories with the change log, with cl:slots added. */
	static final String CHANGELOG_TTL = """
			@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
			@prefix config: <tag:rdf4j.org,2023:config/>.
			@prefix cl: <tag:fau-cdi.github.io,2026:opengdb/changelog#>.
			[] a config:Repository ;
			config:rep.id "test" ;
			rdfs:label "Test" ;
			config:rep.impl [
			    config:rep.type "openrdf:SailRepository" ;
			    config:sail.impl [
			        config:sail.type "opengdb:ChangeLogSail" ;
			        cl:slots 50 ;
			        config:delegate [
			            config:sail.type "openrdf:NativeStore" ;
			            config:native.tripleIndexes "spoc,posc,cosp"
			        ]
			    ]
			].
			""";

	static final String PLAIN_TTL = """
			@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
			@prefix config: <tag:rdf4j.org,2023:config/>.
			[] a config:Repository ;
			config:rep.id "test" ;
			rdfs:label "Test" ;
			config:rep.impl [
			    config:rep.type "openrdf:SailRepository" ;
			    config:sail.impl [
			        config:sail.type "openrdf:NativeStore" ;
			        config:native.tripleIndexes "spoc,posc,cosp"
			    ]
			].
			""";

	@TempDir
	Path dir;

	@Test
	void parsesAndExportsWithDelegate() throws IOException {
		Model model = Rio.parse(new StringReader(CHANGELOG_TTL), RDFFormat.TURTLE);
		Resource implNode = Models.objectResource(model.getStatements(null, CONFIG.Sail.impl, null)).orElseThrow();

		SailImplConfig parsed = SailConfigUtil.parseRepositoryImpl(model, implNode);

		ChangeLogSailConfig config = assertInstanceOf(ChangeLogSailConfig.class, parsed);
		assertEquals(50, config.getSlots());
		assertEquals(ChangeLogSail.DEFAULT_MAX_NODES, config.getMaxNodes());
		NativeStoreConfig delegate = assertInstanceOf(NativeStoreConfig.class, config.getDelegate());
		assertEquals("spoc,posc,cosp", delegate.getTripleIndexes());
		config.validate();

		Model exported = new LinkedHashModel();
		Resource node = config.export(exported);
		assertTrue(exported.contains(node, CONFIG.delegate, null));
		ChangeLogSailConfig again = assertInstanceOf(ChangeLogSailConfig.class,
				SailConfigUtil.parseRepositoryImpl(exported, node));
		assertEquals(50, again.getSlots());
		assertEquals("spoc,posc,cosp", ((NativeStoreConfig) again.getDelegate()).getTripleIndexes());
	}

	@Test
	void rejectsInvalidValues() throws IOException {
		Model model = Rio.parse(new StringReader(CHANGELOG_TTL.replace("cl:slots 50", "cl:slots 0")),
				RDFFormat.TURTLE);
		Resource implNode = Models.objectResource(model.getStatements(null, CONFIG.Sail.impl, null)).orElseThrow();
		SailImplConfig parsed = SailConfigUtil.parseRepositoryImpl(model, implNode);
		assertThrows(SailConfigException.class, parsed::validate);

		ChangeLogSailConfig noDelegate = new ChangeLogSailConfig();
		assertThrows(SailConfigException.class, noDelegate::validate);
	}

	@Test
	void repositoryManagerBuildsTheStackAndKeepsDataWhenSwitched() throws IOException {
		LocalRepositoryManager manager = new LocalRepositoryManager(dir.toFile());
		manager.init();
		try {
			// A plain repository with data, as authproxy creates it without the change log.
			manager.addRepositoryConfig(config(PLAIN_TTL));
			Repository plain = manager.getRepository("test");
			try (RepositoryConnection con = plain.getConnection()) {
				con.add(ex("s"), ex("p"), ex("o"), ex("g"));
			}

			// What enable_changelog does: update config.ttl, then restart.
			manager.addRepositoryConfig(config(CHANGELOG_TTL));
			manager.shutDown();
			manager = new LocalRepositoryManager(dir.toFile());
			manager.init();

			SailRepository repository = assertInstanceOf(SailRepository.class, manager.getRepository("test"));
			ChangeLogSail sail = assertInstanceOf(ChangeLogSail.class, repository.getSail());
			assertInstanceOf(NativeStore.class, sail.getBaseSail());
			assertEquals(50, sail.getSlots());
			try (RepositoryConnection con = repository.getConnection()) {
				assertTrue(con.hasStatement(ex("s"), ex("p"), ex("o"), false, ex("g")));
				con.add(ex("s2"), ex("p"), ex("o"), ex("g"));
				assertTrue(con.hasStatement(null, ChangeLogVocabulary.NODE, ex("s2"), false,
						ChangeLogVocabulary.LOG_GRAPH));
			}
		} finally {
			manager.shutDown();
		}
	}

	private static RepositoryConfig config(String turtle) throws IOException {
		Model model = Rio.parse(new StringReader(turtle), RDFFormat.TURTLE);
		Resource node = Models.subject(model.getStatements(null, CONFIG.Rep.id, null)).orElseThrow();
		return RepositoryConfig.create(model, node);
	}
}
