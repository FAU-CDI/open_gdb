package de.fau.cdi.opengdb.changelog;

import java.util.Optional;
import java.util.function.Supplier;

import org.eclipse.rdf4j.collection.factory.api.CollectionFactory;
import org.eclipse.rdf4j.query.Dataset;
import org.eclipse.rdf4j.query.algebra.evaluation.EvaluationStrategy;
import org.eclipse.rdf4j.query.algebra.evaluation.EvaluationStrategyFactory;
import org.eclipse.rdf4j.query.algebra.evaluation.QueryOptimizerPipeline;
import org.eclipse.rdf4j.query.algebra.evaluation.TripleSource;
import org.eclipse.rdf4j.query.algebra.evaluation.federation.FederatedServiceResolver;
import org.eclipse.rdf4j.query.algebra.evaluation.federation.FederatedServiceResolverClient;
import org.eclipse.rdf4j.query.algebra.evaluation.impl.EvaluationStatistics;

/**
 * The store's evaluation strategy factory, with the log graph hidden from the triple source. The
 * store keeps its strategy, optimizers and statistics; SPARQL queries and the WHERE part of updates
 * just don't see log entries unless they name the log graph.
 */
class LogHidingEvaluationStrategyFactory implements EvaluationStrategyFactory, FederatedServiceResolverClient {

	private final EvaluationStrategyFactory delegate;

	LogHidingEvaluationStrategyFactory(EvaluationStrategyFactory delegate) {
		this.delegate = delegate;
	}

	@Override
	public EvaluationStrategy createEvaluationStrategy(Dataset dataset, TripleSource tripleSource,
			EvaluationStatistics evaluationStatistics) {
		return delegate.createEvaluationStrategy(dataset, LogHidingTripleSource.wrap(tripleSource),
				evaluationStatistics);
	}

	@Override
	@Deprecated
	public void setQuerySolutionCacheThreshold(long threshold) {
		delegate.setQuerySolutionCacheThreshold(threshold);
	}

	@Override
	public long getQuerySolutionCacheThreshold() {
		return delegate.getQuerySolutionCacheThreshold();
	}

	@Override
	public void setOptimizerPipeline(QueryOptimizerPipeline pipeline) {
		delegate.setOptimizerPipeline(pipeline);
	}

	@Override
	public Optional<QueryOptimizerPipeline> getOptimizerPipeline() {
		return delegate.getOptimizerPipeline();
	}

	@Override
	public boolean isTrackResultSize() {
		return delegate.isTrackResultSize();
	}

	@Override
	public void setTrackResultSize(boolean trackResultSize) {
		delegate.setTrackResultSize(trackResultSize);
	}

	@Override
	public void setCollectionFactory(Supplier<CollectionFactory> collectionFactory) {
		delegate.setCollectionFactory(collectionFactory);
	}

	@Override
	public void setFederatedServiceResolver(FederatedServiceResolver resolver) {
		if (delegate instanceof FederatedServiceResolverClient client) {
			client.setFederatedServiceResolver(resolver);
		}
	}

	@Override
	public FederatedServiceResolver getFederatedServiceResolver() {
		return delegate instanceof FederatedServiceResolverClient client ? client.getFederatedServiceResolver()
				: null;
	}
}
