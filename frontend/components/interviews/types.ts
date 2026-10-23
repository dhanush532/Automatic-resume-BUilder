export type Evaluation = {
  score: number; accuracy: number; relevance: number; clarity: number; feedback: string;
  strengths: string[]; weaknesses: string[]; corrections: string[]; sample_answer: string;
  recommendations: string[]; follow_up: string;
};
export type Turn = { id: string; text: string; category: string; difficulty: number; answer?: string; evaluation?: Evaluation };
export type Report = {
  score: number | null; accuracy: number | null; relevance: number | null; clarity: number | null;
  answered: number; planned: number; strengths: string[]; weaknesses: string[]; recommendations: string[]; note: string;
};
export type Interview = {
  id: string; role: string; interview_type: string; difficulty: number; duration_minutes: number; question_count: number;
  status: "active" | "paused" | "completed"; elapsed_seconds: number; created_at: string; revision: number;
  model: string; turns: Turn[]; report: Report;
};
export const interviewTypes = ["mixed", "technical", "hr", "behavioral", "project", "resume"];
