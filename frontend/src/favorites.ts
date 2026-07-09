import type { GazetteerFile, LocalOldPicture } from "./types";

const gazetteerFavoritesKey = "rag_favorite_gazetteers";
const pictureFavoritesKey = "rag_favorite_old_pictures";

export type FavoriteGazetteer = GazetteerFile & {
  favorited_at: string;
};

export type FavoriteOldPicture = LocalOldPicture & {
  favorited_at: string;
};

export function loadFavoriteGazetteers(): FavoriteGazetteer[] {
  return loadFavorites<FavoriteGazetteer>(gazetteerFavoritesKey);
}

export function loadFavoriteOldPictures(): FavoriteOldPicture[] {
  return loadFavorites<FavoriteOldPicture>(pictureFavoritesKey);
}

export function isGazetteerFavorited(fullPath: string) {
  return loadFavoriteGazetteers().some((item) => item.full_path === fullPath);
}

export function isOldPictureFavorited(taskId: string) {
  return loadFavoriteOldPictures().some((item) => item.local_download_task_id === taskId);
}

export function toggleFavoriteGazetteer(item: GazetteerFile): boolean {
  const current = loadFavoriteGazetteers();
  const exists = current.some((favorite) => favorite.full_path === item.full_path);
  const next = exists
    ? current.filter((favorite) => favorite.full_path !== item.full_path)
    : [{ ...item, favorited_at: new Date().toISOString() }, ...current];
  saveFavorites(gazetteerFavoritesKey, next);
  return !exists;
}

export function toggleFavoriteOldPicture(item: LocalOldPicture): boolean {
  const current = loadFavoriteOldPictures();
  const exists = current.some((favorite) => favorite.local_download_task_id === item.local_download_task_id);
  const next = exists
    ? current.filter((favorite) => favorite.local_download_task_id !== item.local_download_task_id)
    : [{ ...item, favorited_at: new Date().toISOString() }, ...current];
  saveFavorites(pictureFavoritesKey, next);
  return !exists;
}

export function removeFavoriteGazetteer(fullPath: string): void {
  saveFavorites(
    gazetteerFavoritesKey,
    loadFavoriteGazetteers().filter((item) => item.full_path !== fullPath),
  );
}

export function removeFavoriteOldPicture(taskId: string): void {
  saveFavorites(
    pictureFavoritesKey,
    loadFavoriteOldPictures().filter((item) => item.local_download_task_id !== taskId),
  );
}

function loadFavorites<T>(key: string): T[] {
  const raw = localStorage.getItem(key);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    localStorage.removeItem(key);
    return [];
  }
}

function saveFavorites<T>(key: string, items: T[]): void {
  localStorage.setItem(key, JSON.stringify(items));
}
