/** The site Worker: `POST /e` events, and the static assets for any other path that reaches it. */
import { handle } from './handle';

interface Bindings {
  ASSETS: Fetcher;
  EVENTS: AnalyticsEngineDataset;
  EVENTS_KEY?: string;
}

export default {
  fetch: (request, env) => handle(request, env),
} satisfies ExportedHandler<Bindings>;
