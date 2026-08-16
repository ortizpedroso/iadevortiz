export type Message = {
  role: string;
  content: string;
  agent?: string;
};

export type TaskNode = {
  id: string;
  title: string;
  status?: string;
  children?: TaskNode[];
};

export type SessionSnapshot = {
  provider?: string;
  model?: string;
  project?: string | null;
  project_name?: string;
  phase?: string;
  provider_ok?: boolean;
  provider_error?: string;
  project_preview?: { available?: boolean; path?: string; entry?: string };
  tasks?: TaskNode[];
  database?: boolean;
};

export type WsEvent = {
  type: string;
  message?: string;
  content?: string;
  role?: string;
  agent?: string;
  tasks?: TaskNode[];
  project_preview?: SessionSnapshot["project_preview"];
  [key: string]: unknown;
};
