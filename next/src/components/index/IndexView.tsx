'use client';
/** The index in the address's state; it reads the query string, so it renders only in the browser. */
import type { FilterDefaults } from './filter';
import { IndexBody, type IndexData } from './IndexBody';
import { useDeviceAspect, useIndexState } from './use-index-state';

export interface IndexViewProps extends IndexData {
  /** The build's first sort and the orders the form offers; the shape default is the device's. */
  sorting: Omit<FilterDefaults, 'shape'>;
}

export function IndexView({ sorting, ...data }: IndexViewProps) {
  const home = useDeviceAspect();
  const defaults = { ...sorting, shape: home };
  const [state, setState] = useIndexState(defaults);
  return <IndexBody {...data} state={state} defaults={defaults} home={home} onChange={setState} />;
}
