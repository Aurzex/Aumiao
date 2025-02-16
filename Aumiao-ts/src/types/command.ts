export type ProgramDefinition = {
	name: string;
	description: string;
	version: string;
};

export type CommandDefinition = {
	name: string;
	description: string;
	options?: {
		flags: string;
		description: string;
		defaultValue?: any;
	}[];
	children?: CommandDefinition[];
};
