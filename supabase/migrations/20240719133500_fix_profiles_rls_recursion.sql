-- =====================================================
-- Fix: Infinite Recursion in RLS policies for profiles/projects/designs
-- Creates a SECURITY DEFINER function to check admin status without triggering RLS.
-- =====================================================

-- 1. Create SECURITY DEFINER function to bypass RLS when checking admin status
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

-- 2. Drop existing recursive policies
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;

DROP POLICY IF EXISTS "Users can manage own projects" ON public.projects;
DROP POLICY IF EXISTS "Admins can view all projects" ON public.projects;

DROP POLICY IF EXISTS "Users can manage own designs" ON public.system_designs;
DROP POLICY IF EXISTS "Admins can view all designs" ON public.system_designs;

-- 3. Re-create clean, non-recursive policies using public.is_admin()

-- Profiles
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

-- System Designs
CREATE POLICY "Designs all policy"
  ON public.system_designs FOR ALL
  USING (auth.uid() = user_id OR public.is_admin());
