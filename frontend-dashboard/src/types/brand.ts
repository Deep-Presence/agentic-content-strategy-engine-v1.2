export interface Project {
  id: string;
  name: string;
  slug: string;
  description?: string;
  personas: Persona[];
  style_guide?: string;
  knowledge_docs: KnowledgeDoc[];
  created_at: string;
}

export interface Persona {
  id: string;
  name: string;
  type: 'icp' | 'secondary';
  content: string;
  project_id?: string;
}

export interface KnowledgeDoc {
  id: string;
  title: string;
  type: 'brand_guidelines' | 'product_context' | 'voice_recording' | 'style_guide' | 'images' | 'other';
  content: string;
  project_id?: string;
}
