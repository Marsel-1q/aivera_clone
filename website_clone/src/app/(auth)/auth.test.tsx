import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import LoginPage from './login/page'
import SignupPage from './signup/page'

// Mock useRouter
const pushMock = vi.fn()
const refreshMock = vi.fn()
vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: pushMock,
        refresh: refreshMock,
    }),
}))

// Mock Supabase client
const signInWithPasswordMock = vi.fn()
const signUpMock = vi.fn()

vi.mock('@/lib/supabase/client', () => ({
    createClient: () => ({
        auth: {
            signInWithPassword: signInWithPasswordMock,
            signUp: signUpMock,
        },
    }),
}))

describe('Auth Pages', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    describe('LoginPage', () => {
        it('renders login form', () => {
            render(<LoginPage />)
            expect(screen.getByLabelText(/email/i)).toBeDefined()
            expect(screen.getByLabelText(/password/i)).toBeDefined()
            expect(screen.getByRole('button', { name: /login/i })).toBeDefined()
        })

        it('succesfully logs in', async () => {
            signInWithPasswordMock.mockResolvedValueOnce({ error: null })
            render(<LoginPage />)

            fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'test@example.com' } })
            fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } })
            fireEvent.click(screen.getByRole('button', { name: /login/i }))

            await waitFor(() => {
                expect(signInWithPasswordMock).toHaveBeenCalledWith({
                    email: 'test@example.com',
                    password: 'password123',
                })
                expect(pushMock).toHaveBeenCalledWith('/dashboard')
            })
        })

        it('handles login error', async () => {
            signInWithPasswordMock.mockResolvedValueOnce({ error: { message: 'Invalid credentials' } })
            render(<LoginPage />)

            fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'test@example.com' } })
            fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrongpass' } })
            fireEvent.click(screen.getByRole('button', { name: /login/i }))

            await waitFor(() => {
                expect(signInWithPasswordMock).toHaveBeenCalled()
                expect(pushMock).not.toHaveBeenCalled()
            })
        })
    })

    describe('SignupPage', () => {
        it('calls signUp with correct data', async () => {
            signUpMock.mockResolvedValueOnce({ error: null })
            render(<SignupPage />)

            fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: 'John' } })
            fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: 'Doe' } })
            fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'john@example.com' } })
            fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } })
            fireEvent.change(screen.getByLabelText(/date of birth/i), { target: { value: '1990-01-01' } })
            fireEvent.change(screen.getByLabelText(/country/i), { target: { value: 'Wonderland' } })

            fireEvent.click(screen.getByRole('button', { name: /continue/i }))

            await waitFor(() => {
                expect(signUpMock).toHaveBeenCalledWith({
                    email: 'john@example.com',
                    password: 'password123',
                    options: {
                        data: {
                            full_name: 'John Doe',
                            dob: '1990-01-01',
                            country: 'Wonderland'
                        }
                    }
                })
                expect(pushMock).toHaveBeenCalledWith('/dashboard')
            })
        })
    })
})
