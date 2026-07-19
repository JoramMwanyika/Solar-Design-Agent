-- =====================================================
-- Solar Design Agent — Supabase Schema
-- Run this in the Supabase SQL Editor
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
-- 4. System Designs (Sizing Results)
-- -----------------------------------------------
CREATE TABLE IF NOT EXISTS public.system_designs (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id      UUID REFERENCES public.projects(id) ON DELETE CASCADE,
  user_id         UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  chat_session_id UUID REFERENCES public.chat_sessions(id) ON DELETE SET NULL,
  system_type     TEXT,
  inputs          JSONB DEFAULT '{}',   -- raw inputs from user/site report
  sizing_results  JSONB DEFAULT '{}',   -- calculated sizing data
  boq_data        JSONB DEFAULT '[]',   -- BOQ line items (qty only)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------
-- 5. Row Level Security (RLS) & Policies
-- -----------------------------------------------
ALTER TABLE public.profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_designs ENABLE ROW LEVEL SECURITY;

-- Helper function to check admin role without triggering recursive RLS
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM public.profiles
    WHERE id = auth.uid() AND role = 'admin'
  );
END;
$$;

-- Profiles: users see/update own, admins see/update all
CREATE POLICY "Profiles select policy"
  ON public.profiles FOR SELECT
  USING (auth.uid() = id OR public.is_admin());

CREATE POLICY "Profiles update policy"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id OR public.is_admin());

-- Projects
CREATE POLICY "Projects all policy"
  ON public.projects FOR ALL
  USING (auth.uid() = user_id OR public.is_admin());

-- Chat Sessions
CREATE POLICY "Users can manage own sessions"
  ON public.chat_sessions FOR ALL
  USING (auth.uid() = user_id);

-- System Designs
CREATE POLICY "Designs all policy"
  ON public.system_designs FOR ALL
  USING (auth.uid() = user_id OR public.is_admin());

-- -----------------------------------------------
-- 6. Helper function: update updated_at
-- -----------------------------------------------
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_projects_updated_at
  BEFORE UPDATE ON public.projects
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_chat_sessions_updated_at
  BEFORE UPDATE ON public.chat_sessions
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
