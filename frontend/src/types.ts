export type ChatItem = {
  id: string;
  title?: string;
  project_slug?: string | null;
  phase?: string;
  is_active?: boolean;
  updated_at?: string;
};

export type ProjectItem = {
  id?: string;
  slug: string;
  name?: string;
  is_active?: boolean;
};

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

export type SpecPreview = {
  name?: string;
  title?: string;
  status?: string;
  suggested_stack?: Record<string, string>;
  confirmed_stack?: Record<string, string>;
  effective_stack?: Record<string, string>;
  body?: string;
  markdown?: string;
};

export type SessionSnapshot = {
  provider?: string;
  model?: string;
  project?: string | null;
  project_name?: string;
  phase?: string;
  active_spec?: string | null;
  spec_status?: string | null;
  spec_preview?: SpecPreview | null;
  provider_ok?: boolean;
  provider_error?: string;
  provider_pool?: string[];
  project_preview?: { available?: boolean; path?: string; entry?: string };
  tasks?: TaskNode[];
  database?: boolean;
  goal?: string;
  active_agent?: string | null;
  last_agent?: string;
  library?: { chats?: ChatItem[]; projects?: ProjectItem[]; active_chat_id?: string | null };
};

export type LibrarySnapshot = {
  chats: ChatItem[];
  projects: ProjectItem[];
  active_chat_id?: string | null;
};

export type WsEvent = {
  type: string;
  message?: string;
  content?: string;
  role?: string;
  agent?: string;
  tasks?: TaskNode[];
  spec?: SpecPreview;
  spec_preview?: SpecPreview | null;
  project_preview?: SessionSnapshot["project_preview"];
  [key: string]: unknown;
};
