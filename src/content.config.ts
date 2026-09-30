import { defineCollection } from 'astro:content';
import { wallpapers } from './server/catalog/loader';
import { wallpaper } from './server/catalog/schema';

export const collections = {
  wallpapers: defineCollection({ loader: wallpapers(), schema: wallpaper }),
};
