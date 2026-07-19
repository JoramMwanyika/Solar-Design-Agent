-- =====================================================
-- Migration: 20240101000000_initial_schema.sql
-- Solar Design Agent — Initial Database Schema (Idempotent)
-- =====================================================

-- -----------------------------------------------
-- 1. Profiles (extends Supabase auth.users)
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id          UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  full_name   TEXT NOT NULL,
  role        TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
  is_active   BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-create profile on new user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email),
    COALESCE(NEW.raw_user_meta_data->>'role', 'user')
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- -----------------------------------------------
-- 2. Projects
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS public.projects (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id      UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  name         TEXT NOT NULL,
  system_type  TEXT CHECK (system_type IN ('off-grid', 'hybrid', 'grid-tied')),
  location     TEXT,
  description  TEXT,
  status       TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'archived')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------
-- 3. Chat Sessions
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS public.chat_sessions (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id   UUID REFERENCES public.projects(id) ON DELETE CASCADE,
  user_id      UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  title        TEXT DEFAULT 'New Chat',
  messages     JSONB NOT NULL DEFAULT '[]',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------
-- 4. System Designs (Sizing Results + BOQ)
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS public.system_designs (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id      UUID REFERENCES public.projects(id) ON DELETE CASCADE,
  user_id         UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  chat_session_id UUID REFERENCES public.chat_sessions(id) ON DELETE SET NULL,
  system_type     TEXT,
  inputs          JSONB DEFAULT '{}',
  sizing_results  JSONB DEFAULT '{}',
  boq_data        JSONB DEFAULT '[]',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------
-- 5. Row Level Security (RLS) & Policies
-- -----------------------------------------------
ALTER TABLE public.profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_designs ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any before re-creating cleanly
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;

DROP POLICY IF EXISTS "Users can manage own projects" ON public.projects;
DROP POLICY IF EXISTS "Admins can view all projects" ON public.projects;

DROP POLICY IF EXISTS "Users can manage own sessions" ON public.chat_sessions;

DROP POLICY IF EXISTS "Users can manage own designs" ON public.system_designs;
DROP POLICY IF EXISTS "Admins can view all designs" ON public.system_designs;

-- Profiles: users see own, admins see all
CREATE POLICY "Users can view own profile"
  ON public.profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Admins can view all profiles"
  ON public.profiles FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role = 'admin'
  ));

CREATE POLICY "Users can update own profile"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id);

-- Projects
CREATE POLICY "Users can manage own projects"
  ON public.projects FOR ALL
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all projects"
  ON public.projects FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role = 'admin'
  ));

-- Chat Sessions
CREATE POLICY "Users can manage own sessions"
  ON public.chat_sessions FOR ALL
  USING (auth.uid() = user_id);

-- System Designs
CREATE POLICY "Users can manage own designs"
  ON public.system_designs FOR ALL
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all designs"
  ON public.system_designs FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM public.profiles p WHERE p.id = auth.uid() AND p.role = 'admin'
  ));

-- -----------------------------------------------
-- 6. updated_at trigger helper
-- -----------------------------------------------
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_profiles_updated_at ON public.profiles;
CREATE TRIGGER update_profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_projects_updated_at ON public.projects;
CREATE TRIGGER update_projects_updated_at
  BEFORE UPDATE ON public.projects
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON public.chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
  BEFORE UPDATE ON public.chat_sessions
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
