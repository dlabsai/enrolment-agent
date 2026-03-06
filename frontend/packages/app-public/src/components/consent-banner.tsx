import { ErrorDialog } from "@va/shared/components/dialog";
import { Button } from "@va/shared/components/ui/button";
import {
    Card,
    CardContent,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@va/shared/components/ui/card";
import {
    Form,
    FormControl,
    FormField,
    FormItem,
    FormMessage,
} from "@va/shared/components/ui/form";
import { Input } from "@va/shared/components/ui/input";
import {
    AI_TERMS_URL,
    CONSENT_COMMUNICATIONS_URL,
    PRIVACY_POLICY_URL,
    TERMS_URL,
    UNIVERSITY_NAME,
} from "@va/shared/config";
import { logger } from "@va/shared/lib/logger";
import { type ChangeEvent, type JSX, useState } from "react";
import { useForm } from "react-hook-form";

import { submitConsentData } from "../lib/consent-api";
import {
    getChatId,
    getConsentChatIds,
    getUserId,
    setConsentData,
} from "../lib/storage";

interface ConsentFormValues {
    firstName: string;
    lastName: string;
    email: string;
    phone: string;
    zip: string;
}

interface ConsentBannerProps {
    onAccept: () => void;
    onDecline: () => void;
}

const formatPhoneNumber = (value: string): string => {
    const numbers = value.replaceAll(/\D/gu, "");
    if (numbers.length === 0) {
        return "";
    }
    if (numbers.length <= 3) {
        return `(${numbers}`;
    }
    if (numbers.length <= 6) {
        return `(${numbers.slice(0, 3)}) ${numbers.slice(3)}`;
    }
    return `(${numbers.slice(0, 3)}) ${numbers.slice(3, 6)}-${numbers.slice(6, 10)}`;
};

const formatZipCode = (value: string): string => {
    const numbers = value.replaceAll(/\D/gu, "");
    return numbers.slice(0, 5);
};

export const ConsentBanner = ({
    onAccept,
    onDecline,
}: ConsentBannerProps): JSX.Element => {
    const [errorDialogOpen, setErrorDialogOpen] = useState(false);

    const form = useForm<ConsentFormValues>({
        defaultValues: {
            firstName: "",
            lastName: "",
            email: "",
            phone: "",
            zip: "",
        },
        mode: "onBlur",
    });

    const handleSubmit = async (values: ConsentFormValues): Promise<void> => {
        const consentData = {
            firstName: values.firstName,
            lastName: values.lastName,
            email: values.email,
            phone: values.phone,
            zip: values.zip,
            timestamp: Date.now(),
        };

        logger.log("Consent form submitted:", consentData);

        setConsentData(consentData);

        getUserId();

        const chatIds: string[] = [];
        const currentChatId = getChatId();
        if (currentChatId !== undefined && currentChatId !== "") {
            chatIds.push(currentChatId);
        }

        const storedChatIds = getConsentChatIds();
        chatIds.push(...storedChatIds);

        const uniqueChatIds = [...new Set(chatIds)];

        const result = await submitConsentData(consentData, uniqueChatIds);

        if (result.success) {
            logger.log("Consent data submitted to backend successfully");
            onAccept();
        } else {
            logger.error("Failed to submit consent to backend:", result.error);
            setErrorDialogOpen(true);
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>Before you continue</CardTitle>
            </CardHeader>
            <Form {...form}>
                <form
                    onSubmit={(event) => {
                        void form.handleSubmit(handleSubmit)(event);
                    }}
                >
                    <CardContent className="space-y-4">
                        <FormField
                            control={form.control}
                            name="firstName"
                            render={({ field, fieldState }) => (
                                <FormItem>
                                    <FormControl>
                                        <Input
                                            placeholder="First name"
                                            {...field}
                                            className={
                                                fieldState.error
                                                    ? "border-destructive"
                                                    : ""
                                            }
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                            rules={{
                                required: "First name is required",
                                minLength: {
                                    value: 2,
                                    message:
                                        "First name must be at least 2 characters",
                                },
                            }}
                        />
                        <FormField
                            control={form.control}
                            name="lastName"
                            render={({ field, fieldState }) => (
                                <FormItem>
                                    <FormControl>
                                        <Input
                                            placeholder="Last name"
                                            {...field}
                                            className={
                                                fieldState.error
                                                    ? "border-destructive"
                                                    : ""
                                            }
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                            rules={{
                                required: "Last name is required",
                                minLength: {
                                    value: 2,
                                    message:
                                        "Last name must be at least 2 characters",
                                },
                            }}
                        />
                        <FormField
                            control={form.control}
                            name="email"
                            render={({ field, fieldState }) => (
                                <FormItem>
                                    <FormControl>
                                        <Input
                                            placeholder="Email"
                                            type="email"
                                            {...field}
                                            className={
                                                fieldState.error
                                                    ? "border-destructive"
                                                    : ""
                                            }
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                            rules={{
                                required: "Email is required",
                                pattern: {
                                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/iu,
                                    message: "Please enter a valid email",
                                },
                            }}
                        />
                        <FormField
                            control={form.control}
                            name="phone"
                            render={({ field, fieldState }) => (
                                <FormItem>
                                    <FormControl>
                                        <Input
                                            {...field}
                                            className={
                                                fieldState.error
                                                    ? "border-destructive"
                                                    : ""
                                            }
                                            onChange={(
                                                event: ChangeEvent<HTMLInputElement>,
                                            ) => {
                                                const numbers =
                                                    event.target.value.replaceAll(
                                                        /\D/gu,
                                                        "",
                                                    );
                                                field.onChange(
                                                    numbers.slice(0, 10),
                                                );
                                            }}
                                            placeholder="Phone"
                                            type="tel"
                                            value={formatPhoneNumber(
                                                field.value,
                                            )}
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                            rules={{
                                required: "Phone is required",
                                validate: (value) =>
                                    value.length === 10 ||
                                    "Phone must be 10 digits",
                            }}
                        />
                        <FormField
                            control={form.control}
                            name="zip"
                            render={({ field, fieldState }) => (
                                <FormItem>
                                    <FormControl>
                                        <Input
                                            {...field}
                                            className={
                                                fieldState.error
                                                    ? "border-destructive"
                                                    : ""
                                            }
                                            onChange={(
                                                event: ChangeEvent<HTMLInputElement>,
                                            ) => {
                                                const numbers =
                                                    event.target.value.replaceAll(
                                                        /\D/gu,
                                                        "",
                                                    );
                                                field.onChange(
                                                    numbers.slice(0, 5),
                                                );
                                            }}
                                            placeholder="Zip"
                                            type="tel"
                                            value={formatZipCode(field.value)}
                                        />
                                    </FormControl>
                                    <FormMessage />
                                </FormItem>
                            )}
                            rules={{
                                required: "Zip is required",
                                validate: (value) =>
                                    value.length === 5 ||
                                    "Zip must be 5 digits",
                            }}
                        />
                        <p className="text-muted-foreground mt-4 text-xs">
                            I consent to the recording of my interaction with
                            this AI Enrollment Agent and agree to{" "}
                            {UNIVERSITY_NAME}'s{" "}
                            <a
                                className="hover:text-foreground underline"
                                href={PRIVACY_POLICY_URL}
                                rel="noopener noreferrer"
                                target="_blank"
                            >
                                Privacy Policy
                            </a>
                            , the website and apps{" "}
                            <a
                                className="hover:text-foreground underline"
                                href={TERMS_URL}
                                rel="noopener noreferrer"
                                target="_blank"
                            >
                                Terms and Conditions
                            </a>
                            ,{" "}
                            <a
                                className="hover:text-foreground underline"
                                href={CONSENT_COMMUNICATIONS_URL}
                                rel="noopener noreferrer"
                                target="_blank"
                            >
                                Consent to Electronic Communications
                            </a>
                            , and the{" "}
                            <a
                                className="hover:text-foreground underline"
                                href={AI_TERMS_URL}
                                rel="noopener noreferrer"
                                target="_blank"
                            >
                                AI Enrollment Agent Terms and Conditions
                            </a>
                            . By starting the enrollment agent, I agree to
                            receive email, SMS and text communications, and
                            phone calls and voicemails from {UNIVERSITY_NAME} at
                            the contact information provided to{" "}
                            {UNIVERSITY_NAME}.
                        </p>
                    </CardContent>
                    <CardFooter className="mt-4 flex justify-end gap-2">
                        <Button
                            onClick={onDecline}
                            size="sm"
                            type="button"
                            variant="outline"
                        >
                            Decline
                        </Button>
                        <Button
                            disabled={form.formState.isSubmitting}
                            size="sm"
                            type="submit"
                        >
                            Accept
                        </Button>
                    </CardFooter>
                </form>
            </Form>

            <ErrorDialog
                description="Failed to submit consent. Please try again."
                onOpenChange={setErrorDialogOpen}
                open={errorDialogOpen}
            />
        </Card>
    );
};
