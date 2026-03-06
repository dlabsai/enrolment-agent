import { Alert, AlertDescription } from "@va/shared/components/ui/alert";
import { Button } from "@va/shared/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@va/shared/components/ui/card";
import {
    Form,
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "@va/shared/components/ui/form";
import { Input } from "@va/shared/components/ui/input";
import { type JSX, useCallback, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { useAuth } from "../contexts/auth-context";
import { loginUser, registerUser } from "../lib/api";

interface FormState {
    name: string;
    email: string;
    password: string;
    confirmPassword: string;
    registration_token: string;
}

type Mode = "login" | "register";

const initialFormState = (): FormState => ({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    registration_token: "",
});

export const AuthPage = (): JSX.Element => {
    const { authenticate, sessionExpired } = useAuth();
    const [mode, setMode] = useState<Mode>("login");
    const [error, setError] = useState<string | undefined>();
    const form = useForm<FormState>({
        defaultValues: initialFormState(),
    });
    const { isSubmitting } = form.formState;
    const activeMode = sessionExpired ? "login" : mode;

    const validatePasswords = useCallback(
        (values: FormState): string | undefined => {
            const validationMessages =
                activeMode === "register"
                    ? [
                          values.password !== values.confirmPassword &&
                              "Passwords do not match",
                          values.password.length < 12 &&
                              "Password must be at least 12 characters",
                          !/[A-Z]/u.test(values.password) &&
                              "Password must include at least one uppercase letter",
                          !/[a-z]/u.test(values.password) &&
                              "Password must include at least one lowercase letter",
                          !/\d/u.test(values.password) &&
                              "Password must include at least one number",
                      ]
                    : [];

            return validationMessages.find(
                (message): message is string => typeof message === "string",
            );
        },
        [activeMode],
    );

    const title = useMemo(
        () =>
            activeMode === "login"
                ? "Sign in to continue"
                : "Register with access token",
        [activeMode],
    );

    const helperText = useMemo(
        () =>
            activeMode === "login"
                ? "Use the email and password you registered with."
                : "Provide your name, email, password, and the registration token you were given.",
        [activeMode],
    );

    let submitLabel = "Register";
    if (isSubmitting) {
        submitLabel = "Working...";
    } else if (activeMode === "login") {
        submitLabel = "Login";
    }

    const handleSubmit = useCallback(
        async (values: FormState) => {
            setError(undefined);

            const passwordError = validatePasswords(values);
            if (passwordError !== undefined) {
                form.setError("password", {
                    message: passwordError,
                    type: "manual",
                });
                return;
            }

            try {
                const response =
                    activeMode === "login"
                        ? await loginUser({
                              email: values.email,
                              password: values.password,
                          })
                        : await registerUser({
                              name: values.name,
                              email: values.email,
                              password: values.password,
                              confirm_password: values.confirmPassword,
                              registration_token: values.registration_token,
                          });
                await authenticate(response.access_token);
            } catch (error) {
                const message =
                    error instanceof Error
                        ? error.message
                        : "Authentication failed";
                setError(message);
            }
        },
        [authenticate, form, activeMode, validatePasswords],
    );

    const toggleMode = useCallback(() => {
        setMode((prev) => (prev === "login" ? "register" : "login"));
        form.reset(initialFormState());
        setError(undefined);
    }, [form]);

    useEffect(() => {
        if (sessionExpired) {
            form.reset(initialFormState());
        }
    }, [form, sessionExpired]);

    return (
        <div className="bg-background text-foreground flex min-h-screen flex-col">
            {sessionExpired && (
                <div className="px-4 pt-4">
                    <Alert>
                        <AlertDescription>
                            Your session has expired — please sign in again.
                        </AlertDescription>
                    </Alert>
                </div>
            )}
            <div className="flex flex-1 items-center justify-center px-4 py-6">
                <Card className="w-full max-w-sm">
                    <CardHeader>
                        <CardTitle className="text-2xl font-semibold">
                            {title}
                        </CardTitle>
                        <CardDescription className="text-muted-foreground">
                            {helperText}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Form {...form}>
                            <form
                                className="space-y-4"
                                onSubmit={(event) => {
                                    void form.handleSubmit(handleSubmit)(event);
                                }}
                            >
                                {activeMode === "register" && (
                                    <FormField
                                        control={form.control}
                                        name="name"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>Name</FormLabel>
                                                <FormControl>
                                                    <Input
                                                        {...field}
                                                        disabled={isSubmitting}
                                                        placeholder="Jane Doe"
                                                        required
                                                    />
                                                </FormControl>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                )}

                                <FormField
                                    control={form.control}
                                    name="email"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Email</FormLabel>
                                            <FormControl>
                                                <Input
                                                    {...field}
                                                    disabled={isSubmitting}
                                                    placeholder="you@example.com"
                                                    required
                                                    type="email"
                                                />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="password"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Password</FormLabel>
                                            <FormControl>
                                                <Input
                                                    {...field}
                                                    disabled={isSubmitting}
                                                    required
                                                    type="password"
                                                />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                {activeMode === "register" && (
                                    <FormField
                                        control={form.control}
                                        name="confirmPassword"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>
                                                    Confirm password
                                                </FormLabel>
                                                <FormControl>
                                                    <Input
                                                        {...field}
                                                        disabled={isSubmitting}
                                                        required
                                                        type="password"
                                                    />
                                                </FormControl>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                )}

                                {activeMode === "register" && (
                                    <FormField
                                        control={form.control}
                                        name="registration_token"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>
                                                    Registration token
                                                </FormLabel>
                                                <FormControl>
                                                    <Input
                                                        {...field}
                                                        disabled={isSubmitting}
                                                        required
                                                        type="password"
                                                    />
                                                </FormControl>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                )}

                                {error !== undefined &&
                                    error !== "" &&
                                    !sessionExpired && (
                                        <Alert variant="destructive">
                                            <AlertDescription>
                                                {error}
                                            </AlertDescription>
                                        </Alert>
                                    )}

                                <div className="flex items-center justify-between gap-4">
                                    <Button
                                        className="flex-1"
                                        disabled={isSubmitting}
                                        type="submit"
                                    >
                                        {submitLabel}
                                    </Button>
                                    {!sessionExpired && (
                                        <Button
                                            disabled={isSubmitting}
                                            onClick={toggleMode}
                                            type="button"
                                            variant="outline"
                                        >
                                            {activeMode === "login"
                                                ? "Need an account? Register"
                                                : "Have an account? Login"}
                                        </Button>
                                    )}
                                </div>
                            </form>
                        </Form>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};
