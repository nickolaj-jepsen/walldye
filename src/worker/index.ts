/** The site Worker's entry, typed against the Workers runtime; handle.ts has the behavior. */
import { handle } from './handle';

interface Bindings {
  ASSETS: Fetcher;
  EVENTS: AnalyticsEngineDataset;
  EVENTS_KEY?: string;
}

export default {
  fetch: (request, env) => handle(request, env),
} satisfies ExportedHandler<Bindings>;
