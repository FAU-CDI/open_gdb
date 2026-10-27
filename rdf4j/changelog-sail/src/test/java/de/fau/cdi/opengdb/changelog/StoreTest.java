package de.fau.cdi.opengdb.changelog;

import java.nio.file.Path;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.io.TempDir;

/**
 * Base of the tests that run over each store type. Subclasses are annotated with
 * {@code @ParameterizedClass @EnumSource(StoreType.class)}; {@link #fixture()} opens the store on
 * first use, so a test can set slots and limits first.
 */
abstract class StoreTest {

	final Fixture.StoreType store;

	@TempDir
	Path dir;

	private Fixture fixture;

	StoreTest(Fixture.StoreType store) {
		this.store = store;
	}

	/** An unopened fixture; call {@link Fixture#open()} after setting its parameters. */
	Fixture configure() {
		if (fixture == null) {
			fixture = new Fixture(store, dir);
		}
		return fixture;
	}

	Fixture fixture() {
		Fixture f = configure();
		if (f.repo == null) {
			f.open();
		}
		return f;
	}

	@AfterEach
	void closeFixture() {
		if (fixture != null) {
			fixture.close();
		}
	}
}
