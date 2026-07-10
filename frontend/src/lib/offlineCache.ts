/** M5: IndexedDB offline cache for projects and chapters. */
const DB_NAME = "novelcraft_offline";
const DB_VERSION = 2;

export type OfflineMutationKind = "content_update" | "ai_operation";
export type OfflineMutationStatus = "pending" | "conflict" | "completed" | "failed";

export type OfflineMutation = {
  id: string;
  kind: OfflineMutationKind;
  url: string;
  method: "POST" | "PUT";
  body: Record<string, unknown>;
  createdAt: number;
  attempts: number;
  status: OfflineMutationStatus;
  result?: unknown;
  error?: string;
};

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("cache")) {
        db.createObjectStore("cache", { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains("mutations")) {
        const mutations = db.createObjectStore("mutations", { keyPath: "id" });
        mutations.createIndex("status", "status", { unique: false });
        mutations.createIndex("createdAt", "createdAt", { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function cacheSet(key: string, value: any): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("cache", "readwrite");
    tx.objectStore("cache").put({ key, value, ts: Date.now() });
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => reject(tx.error);
  });
}

export async function cacheGet<T = any>(key: string): Promise<T | null> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("cache", "readonly");
    const req = tx.objectStore("cache").get(key);
    req.onsuccess = () => { db.close(); resolve(req.result?.value ?? null); };
    req.onerror = () => reject(req.error);
  });
}

export async function cacheDelete(key: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("cache", "readwrite");
    tx.objectStore("cache").delete(key);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => reject(tx.error);
  });
}

export async function enqueueMutation(
  mutation: Omit<OfflineMutation, "createdAt" | "attempts" | "status">,
): Promise<OfflineMutation> {
  const record: OfflineMutation = {
    ...mutation,
    createdAt: Date.now(),
    attempts: 0,
    status: "pending",
  };
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("mutations", "readwrite");
    tx.objectStore("mutations").put(record);
    tx.oncomplete = () => { db.close(); resolve(record); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

export async function listMutations(status?: OfflineMutationStatus): Promise<OfflineMutation[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("mutations", "readonly");
    const store = tx.objectStore("mutations");
    const request = status ? store.index("status").getAll(status) : store.getAll();
    request.onsuccess = () => {
      db.close();
      resolve((request.result as OfflineMutation[]).sort((a, b) => a.createdAt - b.createdAt));
    };
    request.onerror = () => { db.close(); reject(request.error); };
  });
}

export async function updateMutation(id: string, changes: Partial<OfflineMutation>): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("mutations", "readwrite");
    const store = tx.objectStore("mutations");
    const request = store.get(id);
    request.onsuccess = () => {
      if (request.result) store.put({ ...request.result, ...changes, id });
    };
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

export async function deleteMutation(id: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("mutations", "readwrite");
    tx.objectStore("mutations").delete(id);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}
